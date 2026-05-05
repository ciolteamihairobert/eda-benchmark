package integration_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap"

	"github.com/eda-benchmark/go-service/internal/fault"
	"github.com/eda-benchmark/go-service/internal/metrics"
	"github.com/eda-benchmark/go-service/internal/pipeline"
	"github.com/eda-benchmark/go-service/internal/server"
)

// mockProducer is a no-op Kafka producer used to keep integration tests
// independent of a real broker.
type mockProducer struct {
	mock.Mock
}

func (m *mockProducer) Produce(ctx context.Context, topic, key, value string) error {
	args := m.Called(ctx, topic, key, value)
	return args.Error(0)
}

func buildTestServer(t *testing.T) (*httptest.Server, context.CancelFunc) {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())

	prod := &mockProducer{}
	prod.On("Produce", mock.Anything, mock.Anything, mock.Anything, mock.Anything).Return(nil)

	m := metrics.NewOrderMetrics()
	f := fault.New(0, 0.0)
	logger := zap.NewNop()

	eventHandler := pipeline.NewOrderPlacedHandler(m, logger)
	handler := pipeline.NewPlaceOrderHandler("orders.placed", prod, m, f, logger, eventHandler)
	dispatcher := pipeline.NewDispatcher(ctx, 2)

	router := server.NewRouter(ctx, dispatcher, handler, m, logger)
	ts := httptest.NewServer(router)

	t.Cleanup(func() {
		ts.Close()
		cancel()
	})

	return ts, cancel
}

func validOrderJSON(orderID string) []byte {
	order := map[string]any{
		"orderId":    orderID,
		"customerId": "cust-integration-1",
		"items": []map[string]any{
			{"sku": "SKU-001", "quantity": 1, "price": 9.99},
		},
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}
	b, _ := json.Marshal(order)
	return b
}

func TestPostOrders_ValidPayload_Returns202(t *testing.T) {
	ts, _ := buildTestServer(t)

	resp, err := http.Post(ts.URL+"/orders", "application/json",
		bytes.NewReader(validOrderJSON("ord-integ-1")))
	assert.NoError(t, err)
	defer resp.Body.Close()

	assert.Equal(t, http.StatusAccepted, resp.StatusCode)
	assert.Equal(t, "application/json", resp.Header.Get("Content-Type"))

	var body map[string]string
	assert.NoError(t, json.NewDecoder(resp.Body).Decode(&body))
	assert.Equal(t, "ord-integ-1", body["orderId"])
	assert.Equal(t, "accepted", body["status"])
}

func TestPostOrders_InvalidPayload_Returns400(t *testing.T) {
	ts, _ := buildTestServer(t)

	resp, err := http.Post(ts.URL+"/orders", "application/json",
		strings.NewReader("{}"))
	assert.NoError(t, err)
	defer resp.Body.Close()

	assert.Equal(t, http.StatusBadRequest, resp.StatusCode)
	assert.Contains(t, resp.Header.Get("Content-Type"), "application/problem+json")
}

func TestGetHealth_Returns200(t *testing.T) {
	ts, _ := buildTestServer(t)

	resp, err := http.Get(ts.URL + "/health")
	assert.NoError(t, err)
	defer resp.Body.Close()

	assert.Equal(t, http.StatusOK, resp.StatusCode)

	var body map[string]string
	assert.NoError(t, json.NewDecoder(resp.Body).Decode(&body))
	assert.Equal(t, "ok", body["status"])
}

func TestGetMetrics_Returns200(t *testing.T) {
	ts, _ := buildTestServer(t)

	resp, err := http.Get(ts.URL + "/metrics")
	assert.NoError(t, err)
	defer resp.Body.Close()

	assert.Equal(t, http.StatusOK, resp.StatusCode)
	assert.Contains(t, resp.Header.Get("Content-Type"), "text/plain")
}
