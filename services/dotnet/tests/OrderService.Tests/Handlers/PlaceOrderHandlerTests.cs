using System.Diagnostics;
using FluentAssertions;
using MediatR;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using Xunit;
using OrderService.Api.Fault;
using OrderService.Api.Features.Orders;
using OrderService.Api.Kafka;
using OrderService.Api.Metrics;
using OrderService.Api.Models;

namespace OrderService.Tests.Handlers;

public sealed class PlaceOrderHandlerTests
{
    private readonly Mock<IPublisher> _publisher = new();
    private readonly Mock<IKafkaProducerService> _producer = new();
    private readonly Mock<IOrderMetrics> _metrics = new();

    public PlaceOrderHandlerTests()
    {
        _publisher
            .Setup(x => x.Publish(It.IsAny<INotification>(), It.IsAny<CancellationToken>()))
            .Returns(Task.CompletedTask);

        _producer
            .Setup(x => x.ProduceAsync(
                It.IsAny<string>(), It.IsAny<string>(), It.IsAny<string>(),
                It.IsAny<CancellationToken>()))
            .Returns(Task.CompletedTask);
    }

    private PlaceOrderHandler CreateHandler(FaultSettings? fault = null) => new(
        _publisher.Object,
        _producer.Object,
        _metrics.Object,
        fault ?? new FaultSettings(),
        new KafkaSettings(),
        NullLogger<PlaceOrderHandler>.Instance);

    private static Order CreateOrder(string orderId = "ord-test-1") => new()
    {
        OrderId = orderId,
        CustomerId = "cust-42",
        Items = [new OrderItem { Sku = "SKU-001", Quantity = 2, Price = 19.99m }],
        Timestamp = DateTimeOffset.UtcNow,
    };

    [Fact]
    public async Task Handle_ValidOrder_ReturnsAccepted()
    {
        var handler = CreateHandler();
        var order = CreateOrder("ord-valid-1");

        var result = await handler.Handle(new PlaceOrderCommand(order), CancellationToken.None);

        result.Status.Should().Be("accepted");
        result.OrderId.Should().Be("ord-valid-1");
        result.AcceptedAt.Should().BeCloseTo(DateTimeOffset.UtcNow, TimeSpan.FromSeconds(2));
    }

    [Fact]
    public async Task Handle_ValidOrder_PublishesMediatREventAndProducesToKafka()
    {
        var handler = CreateHandler();
        var order = CreateOrder();

        await handler.Handle(new PlaceOrderCommand(order), CancellationToken.None);

        _publisher.Verify(
            x => x.Publish(It.IsAny<OrderPlacedEvent>(), It.IsAny<CancellationToken>()),
            Times.Once);

        _producer.Verify(
            x => x.ProduceAsync("orders.placed", order.OrderId, It.IsAny<string>(), It.IsAny<CancellationToken>()),
            Times.Once);
    }

    [Fact]
    public async Task Handle_FaultFailRate1_ThrowsOrderProcessingException()
    {
        var handler = CreateHandler(new FaultSettings { FailRate = 1.0 });
        var order = CreateOrder("ord-fault-1");

        var act = () => handler.Handle(new PlaceOrderCommand(order), CancellationToken.None);

        await act.Should().ThrowAsync<OrderProcessingException>()
            .WithMessage("*ord-fault-1*");
    }

    [Fact]
    public async Task Handle_FaultDelayMs_AppliesDelay()
    {
        var handler = CreateHandler(new FaultSettings { DelayMs = 100 });
        var order = CreateOrder();
        var sw = Stopwatch.StartNew();

        await handler.Handle(new PlaceOrderCommand(order), CancellationToken.None);

        sw.Stop();
        sw.ElapsedMilliseconds.Should().BeGreaterOrEqualTo(100);
    }

    [Fact]
    public async Task Handle_ValidOrder_RecordsMetrics()
    {
        var handler = CreateHandler();
        var order = CreateOrder();

        await handler.Handle(new PlaceOrderCommand(order), CancellationToken.None);

        _metrics.Verify(x => x.IncrementOrdersReceived(), Times.Once);
        _metrics.Verify(x => x.RecordProcessingDuration(It.IsAny<double>()), Times.Once);
    }
}
