// .NET equivalent: PlaceOrderHandler : IRequestHandler<PlaceOrderCommand, PlaceOrderResult>

package pipeline

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"go.uber.org/zap"

	"github.com/eda-benchmark/go-service/internal/fault"
	"github.com/eda-benchmark/go-service/internal/metrics"
)

// ProducerClient is the interface for producing messages to Kafka topics.
// Satisfied by *kafka.Producer; extracted here to allow test mocking without
// importing the kafka package (which would pull in real broker dependencies).
type ProducerClient interface {
	Produce(ctx context.Context, topic, key, value string) error
}

// PlaceOrderHandler validates, persists, and dispatches a PlaceOrderCommand.
type PlaceOrderHandler struct {
	topicPlaced  string
	producer     ProducerClient
	metrics      *metrics.OrderMetrics
	fault        *fault.Fault
	logger       *zap.Logger
	eventHandler *OrderPlacedHandler
}

// NewPlaceOrderHandler wires up all dependencies.
func NewPlaceOrderHandler(
	topicPlaced string,
	producer ProducerClient,
	m *metrics.OrderMetrics,
	f *fault.Fault,
	logger *zap.Logger,
	eventHandler *OrderPlacedHandler,
) *PlaceOrderHandler {
	return &PlaceOrderHandler{
		topicPlaced:  topicPlaced,
		producer:     producer,
		metrics:      m,
		fault:        f,
		logger:       logger,
		eventHandler: eventHandler,
	}
}

// Handle executes the order placement pipeline:
// receive → fault inject → publish event → produce to Kafka → return result.
func (h *PlaceOrderHandler) Handle(ctx context.Context, cmd PlaceOrderCommand) (PlaceOrderResult, error) {
	order := cmd.Order
	h.metrics.OrdersReceived.Inc()

	start := time.Now()

	if err := h.fault.Sleep(ctx); err != nil {
		return PlaceOrderResult{}, fmt.Errorf("fault sleep cancelled: %w", err)
	}

	if h.fault.ShouldFail() {
		h.metrics.OrdersFailed.WithLabelValues("processing").Inc()
		h.logger.Error("fault injected", zap.String("orderId", order.OrderID))
		return PlaceOrderResult{}, fmt.Errorf("order %s: %w", order.OrderID, fault.ErrFaultInjected)
	}

	event := OrderPlacedEvent{Order: order, AcceptedAt: time.Now()}
	if err := h.eventHandler.Handle(ctx, event); err != nil {
		h.metrics.OrdersFailed.WithLabelValues("event").Inc()
		h.logger.Error("event handler failed",
			zap.String("orderId", order.OrderID),
			zap.Error(err),
		)
		return PlaceOrderResult{}, fmt.Errorf("event handler: %w", err)
	}

	payload, err := json.Marshal(order)
	if err != nil {
		h.metrics.OrdersFailed.WithLabelValues("serialization").Inc()
		return PlaceOrderResult{}, fmt.Errorf("marshal order %s: %w", order.OrderID, err)
	}

	if err := h.producer.Produce(ctx, h.topicPlaced, order.OrderID, string(payload)); err != nil {
		h.metrics.OrdersFailed.WithLabelValues("kafka").Inc()
		h.logger.Error("produce failed",
			zap.String("orderId", order.OrderID),
			zap.Error(err),
		)
		return PlaceOrderResult{}, fmt.Errorf("produce order %s: %w", order.OrderID, err)
	}

	h.metrics.ProcessingDuration.Observe(time.Since(start).Seconds())

	h.logger.Info("order accepted",
		zap.String("orderId", order.OrderID),
		zap.Int64("durationMs", time.Since(start).Milliseconds()),
	)

	return PlaceOrderResult{
		OrderID:    order.OrderID,
		Status:     "accepted",
		AcceptedAt: time.Now(),
	}, nil
}
