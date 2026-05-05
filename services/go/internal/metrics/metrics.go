// .NET equivalent: OrderMetrics (prometheus-net)

package metrics

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/collectors"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// OrderMetrics holds all Prometheus instruments for the order pipeline.
// Each instance owns its own registry so tests can create isolated instances
// without triggering "already registered" panics.
type OrderMetrics struct {
	registry           *prometheus.Registry
	OrdersReceived     prometheus.Counter
	OrdersPublished    prometheus.Counter
	OrdersProcessed    prometheus.Counter
	OrdersFailed       *prometheus.CounterVec
	ProcessingDuration prometheus.Histogram
}

// NewOrderMetrics creates and registers all metrics on a fresh Prometheus registry.
func NewOrderMetrics() *OrderMetrics {
	reg := prometheus.NewRegistry()
	reg.MustRegister(
		collectors.NewGoCollector(),
		collectors.NewProcessCollector(collectors.ProcessCollectorOpts{}),
	)

	m := &OrderMetrics{
		registry: reg,
		OrdersReceived: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "orders_received_total",
			Help: "Total orders received by the API.",
		}),
		OrdersPublished: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "orders_published_total",
			Help: "Total orders dispatched as in-process events.",
		}),
		OrdersProcessed: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "orders_processed_total",
			Help: "Total orders successfully processed by the consumer.",
		}),
		OrdersFailed: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "orders_failed_total",
			Help: "Total orders that failed, labelled by failure reason.",
		}, []string{"reason"}),
		ProcessingDuration: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "order_processing_duration_seconds",
			Help:    "End-to-end order processing latency in seconds.",
			Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5},
		}),
	}

	reg.MustRegister(
		m.OrdersReceived,
		m.OrdersPublished,
		m.OrdersProcessed,
		m.OrdersFailed,
		m.ProcessingDuration,
	)

	return m
}

// Handler returns an http.Handler that exposes the metrics for this instance.
func (m *OrderMetrics) Handler() http.Handler {
	return promhttp.HandlerFor(m.registry, promhttp.HandlerOpts{})
}
