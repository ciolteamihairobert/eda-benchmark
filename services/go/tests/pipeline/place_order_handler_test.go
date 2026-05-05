package pipeline_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap"

	"github.com/eda-benchmark/go-service/internal/fault"
	"github.com/eda-benchmark/go-service/internal/metrics"
	"github.com/eda-benchmark/go-service/internal/models"
	"github.com/eda-benchmark/go-service/internal/pipeline"
)

// mockProducer satisfies pipeline.ProducerClient using testify/mock.
type mockProducer struct {
	mock.Mock
}

func (m *mockProducer) Produce(ctx context.Context, topic, key, value string) error {
	args := m.Called(ctx, topic, key, value)
	return args.Error(0)
}

func newTestHandler(t *testing.T, f *fault.Fault, prod pipeline.ProducerClient) *pipeline.PlaceOrderHandler {
	t.Helper()
	m := metrics.NewOrderMetrics()
	logger := zap.NewNop()
	eventHandler := pipeline.NewOrderPlacedHandler(m, logger)
	return pipeline.NewPlaceOrderHandler("orders.placed", prod, m, f, logger, eventHandler)
}

func sampleOrder() *models.Order {
	return &models.Order{
		OrderID:    "ord-test-1",
		CustomerID: "cust-42",
		Items:      []models.OrderItem{{SKU: "SKU-001", Quantity: 2, Price: 19.99}},
		Timestamp:  time.Now(),
	}
}

func TestPlaceOrderHandler_ValidOrder_ReturnsAccepted(t *testing.T) {
	prod := &mockProducer{}
	prod.On("Produce", mock.Anything, mock.Anything, mock.Anything, mock.Anything).Return(nil)

	handler := newTestHandler(t, fault.New(0, 0.0), prod)
	result, err := handler.Handle(context.Background(), pipeline.PlaceOrderCommand{Order: sampleOrder()})

	assert.NoError(t, err)
	assert.Equal(t, "accepted", result.Status)
	assert.Equal(t, "ord-test-1", result.OrderID)
	assert.WithinDuration(t, time.Now(), result.AcceptedAt, 2*time.Second)
	prod.AssertExpectations(t)
}

func TestPlaceOrderHandler_FaultFailRate1_ReturnsError(t *testing.T) {
	prod := &mockProducer{}

	handler := newTestHandler(t, fault.New(0, 1.0), prod)
	_, err := handler.Handle(context.Background(), pipeline.PlaceOrderCommand{Order: sampleOrder()})

	assert.Error(t, err)
	assert.True(t, errors.Is(err, fault.ErrFaultInjected))
	prod.AssertNotCalled(t, "Produce")
}

func TestPlaceOrderHandler_FaultDelay_AppliesDelay(t *testing.T) {
	prod := &mockProducer{}
	prod.On("Produce", mock.Anything, mock.Anything, mock.Anything, mock.Anything).Return(nil)

	handler := newTestHandler(t, fault.New(100, 0.0), prod)
	start := time.Now()
	_, err := handler.Handle(context.Background(), pipeline.PlaceOrderCommand{Order: sampleOrder()})
	elapsed := time.Since(start)

	assert.NoError(t, err)
	assert.GreaterOrEqual(t, elapsed.Milliseconds(), int64(90))
}

func TestPlaceOrderHandler_ProducerError_ReturnsError(t *testing.T) {
	prod := &mockProducer{}
	prod.On("Produce", mock.Anything, mock.Anything, mock.Anything, mock.Anything).
		Return(errors.New("broker unavailable"))

	handler := newTestHandler(t, fault.New(0, 0.0), prod)
	_, err := handler.Handle(context.Background(), pipeline.PlaceOrderCommand{Order: sampleOrder()})

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "broker unavailable")
	prod.AssertExpectations(t)
}
