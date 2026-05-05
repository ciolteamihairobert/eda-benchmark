// .NET equivalent: Program.cs endpoints (MapPost /orders, MapGet /health, MapMetrics)

package server

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/pprof"
	"time"

	"go.uber.org/zap"

	"github.com/eda-benchmark/go-service/internal/metrics"
	"github.com/eda-benchmark/go-service/internal/models"
	"github.com/eda-benchmark/go-service/internal/pipeline"
)

// NewRouter builds the HTTP mux with all routes and a logging middleware.
// appCtx is the root application context — it is passed to worker jobs so they
// respect graceful shutdown even after the HTTP request context has expired.
func NewRouter(
	appCtx context.Context,
	dispatcher *pipeline.Dispatcher,
	placeOrderHandler *pipeline.PlaceOrderHandler,
	m *metrics.OrderMetrics,
	logger *zap.Logger,
) http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("POST /orders", handlePlaceOrder(appCtx, dispatcher, placeOrderHandler, logger))
	mux.HandleFunc("GET /health", handleHealth)
	mux.Handle("GET /metrics", m.Handler())

	mux.HandleFunc("GET /debug/pprof/", pprof.Index)
	mux.HandleFunc("GET /debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("GET /debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("GET /debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("GET /debug/pprof/trace", pprof.Trace)

	return loggingMiddleware(mux, logger)
}

func handlePlaceOrder(
	appCtx context.Context,
	dispatcher *pipeline.Dispatcher,
	handler *pipeline.PlaceOrderHandler,
	logger *zap.Logger,
) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var order models.Order
		if err := json.NewDecoder(r.Body).Decode(&order); err != nil {
			writeProblem(w, http.StatusBadRequest, "invalid JSON body", err.Error())
			return
		}

		if err := order.Validate(); err != nil {
			writeProblem(w, http.StatusBadRequest, "validation failed", err.Error())
			return
		}

		orderCopy := order
		err := dispatcher.Dispatch(r.Context(), func() error {
			_, handleErr := handler.Handle(appCtx, pipeline.PlaceOrderCommand{Order: &orderCopy})
			if handleErr != nil {
				logger.Error("handle order failed",
					zap.String("orderId", orderCopy.OrderID),
					zap.Error(handleErr),
				)
			}
			return handleErr
		})

		if errors.Is(err, pipeline.ErrDispatcherFull) {
			writeProblem(w, http.StatusServiceUnavailable, "server overloaded", "try again later")
			return
		}
		if err != nil {
			writeProblem(w, http.StatusInternalServerError, "dispatch failed", err.Error())
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"orderId": order.OrderID,
			"status":  "accepted",
		})
	}
}

func handleHealth(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{
		"status":    "ok",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

func writeProblem(w http.ResponseWriter, status int, title, detail string) {
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"status": status,
		"title":  title,
		"detail": detail,
	})
}

// responseWriter wraps http.ResponseWriter to capture the written status code.
type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func loggingMiddleware(next http.Handler, logger *zap.Logger) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rw := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}
		next.ServeHTTP(rw, r)
		logger.Info("request",
			zap.String("method", r.Method),
			zap.String("path", r.URL.Path),
			zap.Int("status", rw.statusCode),
			zap.Duration("duration", time.Since(start)),
		)
	})
}
