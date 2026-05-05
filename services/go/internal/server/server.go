// .NET equivalent: WebApplication host (app.RunAsync / app.Shutdown)

package server

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"time"

	"go.uber.org/zap"
)

// Server wraps net/http.Server with structured lifecycle methods.
type Server struct {
	httpServer *http.Server
	logger     *zap.Logger
}

// New creates a Server bound to the given port with production-safe timeouts.
func New(port string, handler http.Handler, logger *zap.Logger) *Server {
	return &Server{
		httpServer: &http.Server{
			Addr:         ":" + port,
			Handler:      handler,
			ReadTimeout:  5 * time.Second,
			WriteTimeout: 10 * time.Second,
			IdleTimeout:  120 * time.Second,
		},
		logger: logger,
	}
}

// Start begins accepting connections. Returns nil on graceful shutdown
// (http.ErrServerClosed), or a wrapped error for any other failure.
func (s *Server) Start() error {
	s.logger.Info("http server listening", zap.String("addr", s.httpServer.Addr))
	if err := s.httpServer.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		return fmt.Errorf("http server: %w", err)
	}
	return nil
}

// Shutdown drains active connections then stops the server.
func (s *Server) Shutdown(ctx context.Context) error {
	s.logger.Info("http server shutting down")
	if err := s.httpServer.Shutdown(ctx); err != nil {
		return fmt.Errorf("http server shutdown: %w", err)
	}
	s.logger.Info("http server stopped")
	return nil
}
