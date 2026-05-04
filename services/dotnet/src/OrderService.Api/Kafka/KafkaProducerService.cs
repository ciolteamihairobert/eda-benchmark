using Confluent.Kafka;
using OrderService.Api.Metrics;

namespace OrderService.Api.Kafka;

public interface IKafkaProducerService
{
    Task ProduceAsync(string topic, string key, string value, CancellationToken ct = default);
}

public sealed class KafkaProducerService : BackgroundService, IKafkaProducerService
{
    private readonly IProducer<string, string> _producer;
    private readonly IOrderMetrics _metrics;
    private readonly ILogger<KafkaProducerService> _logger;

    public KafkaProducerService(
        KafkaSettings settings,
        IOrderMetrics metrics,
        ILogger<KafkaProducerService> logger)
    {
        _metrics = metrics;
        _logger = logger;

        var config = new ProducerConfig
        {
            BootstrapServers = settings.BootstrapServers,
            Acks = Acks.All,
            EnableIdempotence = true,
            MessageSendMaxRetries = 3,
            MessageTimeoutMs = 5000,
        };
        _producer = new ProducerBuilder<string, string>(config).Build();
    }

    protected override Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Kafka producer service ready");
        return Task.CompletedTask;
    }

    public async Task ProduceAsync(string topic, string key, string value, CancellationToken ct = default)
    {
        try
        {
            var result = await _producer.ProduceAsync(
                topic,
                new Message<string, string> { Key = key, Value = value },
                ct);

            _logger.LogDebug(
                "Delivered to {TopicPartitionOffset}",
                result.TopicPartitionOffset);
        }
        catch (ProduceException<string, string> ex)
        {
            _logger.LogError(ex, "Produce failed — Topic: {Topic}, Key: {Key}", topic, key);
            _metrics.IncrementOrdersFailed("kafka");
            throw;
        }
    }

    public override async Task StopAsync(CancellationToken cancellationToken)
    {
        _producer.Flush(TimeSpan.FromSeconds(5));
        _producer.Dispose();
        _logger.LogInformation("Kafka producer flushed and disposed");
        await base.StopAsync(cancellationToken);
    }
}
