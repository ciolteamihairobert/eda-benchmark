namespace OrderService.Api.Kafka;

public sealed class KafkaSettings
{
    public string BootstrapServers { get; set; } = "localhost:9092";
    public string GroupId { get; set; } = "dotnet-order-service";

    public string TopicOrdersPlaced { get; set; } = "orders.placed";
    public string TopicOrdersProcessed { get; set; } = "orders.processed";
    public string TopicOrdersFailed { get; set; } = "orders.failed";
}
