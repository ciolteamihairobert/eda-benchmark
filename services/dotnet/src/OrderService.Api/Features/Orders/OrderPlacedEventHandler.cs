using MediatR;
using OrderService.Api.Metrics;

namespace OrderService.Api.Features.Orders;

public sealed class OrderPlacedEventHandler : INotificationHandler<OrderPlacedEvent>
{
    private readonly IOrderMetrics _metrics;
    private readonly ILogger<OrderPlacedEventHandler> _logger;

    public OrderPlacedEventHandler(IOrderMetrics metrics, ILogger<OrderPlacedEventHandler> logger)
    {
        _metrics = metrics;
        _logger = logger;
    }

    public Task Handle(OrderPlacedEvent notification, CancellationToken cancellationToken)
    {
        _logger.LogInformation(
            "OrderPlaced event handled — OrderId: {OrderId}, CustomerId: {CustomerId}, ItemCount: {ItemCount}",
            notification.Order.OrderId,
            notification.Order.CustomerId,
            notification.Order.Items.Count);

        _metrics.IncrementOrdersPublished();
        return Task.CompletedTask;
    }
}
