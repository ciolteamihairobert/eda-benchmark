using System.Text.Json;
using Confluent.Kafka;
using OrderService.Api.Fault;
using OrderService.Api.Metrics;
using OrderService.Api.Models;

namespace OrderService.Api.Kafka;

public sealed class KafkaConsumerService : BackgroundService
{
    private readonly KafkaSettings _settings;
    private readonly IKafkaProducerService _producer;
    private readonly IOrderMetrics _metrics;
    private readonly FaultSettings _fault;
    private readonly ILogger<KafkaConsumerService> _logger;

    public KafkaConsumerService(
        KafkaSettings settings,
        IKafkaProducerService producer,
        IOrderMetrics metrics,
        FaultSettings fault,
        ILogger<KafkaConsumerService> logger)
    {
        _settings = settings;
        _producer = producer;
        _metrics = metrics;
        _fault = fault;
        _logger = logger;
    }

    protected override Task ExecuteAsync(CancellationToken stoppingToken)
    {
        return Task.Run(() => ConsumeLoopAsync(stoppingToken), stoppingToken);
    }

    private async Task ConsumeLoopAsync(CancellationToken ct)
    {
        var config = new ConsumerConfig
        {
            BootstrapServers = _settings.BootstrapServers,
            GroupId = _settings.GroupId,
            AutoOffsetReset = AutoOffsetReset.Earliest,
            EnableAutoCommit = false,
        };

        using var consumer = new ConsumerBuilder<string, string>(config).Build();
        consumer.Subscribe(_settings.TopicOrdersPlaced);
        _logger.LogInformation("Consumer subscribed to {Topic}", _settings.TopicOrdersPlaced);

        try
        {
            while (!ct.IsCancellationRequested)
            {
                ConsumeResult<string, string>? result;
                try
                {
                    result = consumer.Consume(TimeSpan.FromSeconds(1));
                }
                catch (ConsumeException ex)
                {
                    _logger.LogError(ex, "Kafka consume error — {Reason}", ex.Error.Reason);
                    continue;
                }

                if (result is null) continue;

                await ProcessMessageAsync(consumer, result, ct);
            }
        }
        catch (OperationCanceledException) { }
        finally
        {
            consumer.Close();
            _logger.LogInformation("Kafka consumer closed");
        }
    }

    private async Task ProcessMessageAsync(
        IConsumer<string, string> consumer,
        ConsumeResult<string, string> result,
        CancellationToken ct)
    {
        try
        {
            var order = JsonSerializer.Deserialize<Order>(result.Message.Value)
                ?? throw new InvalidOperationException("Deserialized order was null");

            _logger.LogInformation(
                "Processing order — OrderId: {OrderId}, Partition: {Partition}, Offset: {Offset}",
                order.OrderId,
                result.Partition.Value,
                result.Offset.Value);

            if (_fault.DelayMs > 0)
                await Task.Delay(_fault.DelayMs, ct);

            await _producer.ProduceAsync(
                _settings.TopicOrdersProcessed,
                order.OrderId,
                result.Message.Value,
                ct);

            consumer.Commit(result);
            _metrics.IncrementOrdersProcessed();
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to process message — Key: {Key}", result.Message.Key);

            try
            {
                await _producer.ProduceAsync(
                    _settings.TopicOrdersFailed,
                    result.Message.Key ?? string.Empty,
                    result.Message.Value,
                    ct);
            }
            catch (Exception produceEx)
            {
                _logger.LogError(produceEx, "Failed to produce to dead-letter topic");
            }

            consumer.Commit(result);
            _metrics.IncrementOrdersFailed("processing");
        }
    }
}
