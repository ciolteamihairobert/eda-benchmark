using Prometheus;

namespace OrderService.Api.Metrics;

public interface IOrderMetrics
{
    void IncrementOrdersReceived();
    void IncrementOrdersPublished();
    void IncrementOrdersProcessed();
    void IncrementOrdersFailed(string reason);
    void RecordProcessingDuration(double seconds);
}

public sealed class OrderMetrics : IOrderMetrics
{
    private readonly Counter _ordersReceived;
    private readonly Counter _ordersPublished;
    private readonly Counter _ordersProcessed;
    private readonly Counter _ordersFailed;
    private readonly Histogram _processingDuration;

    public OrderMetrics()
    {
        _ordersReceived = Prometheus.Metrics.CreateCounter(
            "orders_received_total",
            "Total orders received by the API.");

        _ordersPublished = Prometheus.Metrics.CreateCounter(
            "orders_published_total",
            "Total orders published as MediatR events.");

        _ordersProcessed = Prometheus.Metrics.CreateCounter(
            "orders_processed_total",
            "Total orders successfully processed by the consumer.");

        _ordersFailed = Prometheus.Metrics.CreateCounter(
            "orders_failed_total",
            "Total orders that failed processing.",
            new CounterConfiguration { LabelNames = ["reason"] });

        _processingDuration = Prometheus.Metrics.CreateHistogram(
            "order_processing_duration_seconds",
            "End-to-end order processing latency in seconds.",
            new HistogramConfiguration
            {
                Buckets = [.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5]
            });
    }

    public void IncrementOrdersReceived() => _ordersReceived.Inc();
    public void IncrementOrdersPublished() => _ordersPublished.Inc();
    public void IncrementOrdersProcessed() => _ordersProcessed.Inc();
    public void IncrementOrdersFailed(string reason) => _ordersFailed.WithLabels(reason).Inc();
    public void RecordProcessingDuration(double seconds) => _processingDuration.Observe(seconds);
}
