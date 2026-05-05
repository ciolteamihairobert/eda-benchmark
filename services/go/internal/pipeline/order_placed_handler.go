// .NET equivalent: OrderPlacedEventHandler : INotificationHandler<OrderPlacedEvent>

package pipeline

import (
	"context"

	"go.uber.org/zap"

	"github.com/eda-benchmark/go-service/internal/metrics"
)

// OrderPlacedHandler handles the in-process OrderPlacedEvent notification,
// mirroring MediatR's INotificationHandler pattern.
type OrderPlacedHandler struct {
	metrics *metrics.OrderMetrics
	logger  *zap.Logger
}

// NewOrderPlacedHandler creates a handler wired to the given metrics and logger.
func NewOrderPlacedHandler(m *metrics.OrderMetrics, logger *zap.Logger) *OrderPlacedHandler {
	return &OrderPlacedHandler{metrics: m, logger: logger}
}

// Handle logs the event and increments the published counter.
func (h *OrderPlacedHandler) Handle(ctx context.Context, event OrderPlacedEvent) error {
	h.logger.Info("OrderPlaced event handled",
		zap.String("orderId", event.Order.OrderID),
		zap.String("customerId", event.Order.CustomerID),
		zap.Int("itemCount", len(event.Order.Items)),
	)
	h.metrics.OrdersPublished.Inc()
	return nil
}
