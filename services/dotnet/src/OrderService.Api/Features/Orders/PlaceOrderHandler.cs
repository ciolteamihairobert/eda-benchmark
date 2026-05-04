using System.Diagnostics;
using System.Text.Json;
using MediatR;
using OrderService.Api.Fault;
using OrderService.Api.Kafka;
using OrderService.Api.Metrics;

namespace OrderService.Api.Features.Orders;

public sealed class PlaceOrderHandler : IRequestHandler<PlaceOrderCommand, PlaceOrderResult>
{
    private readonly IPublisher _publisher;
    private readonly IKafkaProducerService _producer;
    private readonly IOrderMetrics _metrics;
    private readonly FaultSettings _fault;
    private readonly KafkaSettings _kafkaSettings;
    private readonly ILogger<PlaceOrderHandler> _logger;

    public PlaceOrderHandler(
        IPublisher publisher,
        IKafkaProducerService producer,
        IOrderMetrics metrics,
        FaultSettings fault,
        KafkaSettings kafkaSettings,
        ILogger<PlaceOrderHandler> logger)
    {
        _publisher = publisher;
        _producer = producer;
        _metrics = metrics;
        _fault = fault;
        _kafkaSettings = kafkaSettings;
        _logger = logger;
    }

    public async Task<PlaceOrderResult> Handle(PlaceOrderCommand request, CancellationToken cancellationToken)
    {
        var order = request.Order;
        var sw = Stopwatch.StartNew();

        _metrics.IncrementOrdersReceived();

        if (_fault.DelayMs > 0)
            await Task.Delay(_fault.DelayMs, cancellationToken);

        if (_fault.FailRate > 0 && Random.Shared.NextDouble() < _fault.FailRate)
        {
            _metrics.IncrementOrdersFailed("processing");
            throw new OrderProcessingException(order.OrderId, "Fault injection triggered");
        }

        await _publisher.Publish(new OrderPlacedEvent(order, DateTimeOffset.UtcNow), cancellationToken);

        var json = JsonSerializer.Serialize(order);
        await _producer.ProduceAsync(_kafkaSettings.TopicOrdersPlaced, order.OrderId, json, cancellationToken);

        sw.Stop();
        _metrics.RecordProcessingDuration(sw.Elapsed.TotalSeconds);

        _logger.LogInformation(
            "Order accepted — OrderId: {OrderId}, DurationMs: {DurationMs}",
            order.OrderId,
            sw.ElapsedMilliseconds);

        return new PlaceOrderResult(order.OrderId, "accepted", DateTimeOffset.UtcNow);
    }
}

public sealed class OrderProcessingException : Exception
{
    public string OrderId { get; }

    public OrderProcessingException(string orderId, string message)
        : base($"Order '{orderId}' failed: {message}")
    {
        OrderId = orderId;
    }
}
