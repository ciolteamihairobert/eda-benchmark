package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.uber.org/zap"

	"github.com/eda-benchmark/go-service/internal/config"
	"github.com/eda-benchmark/go-service/internal/fault"
	"github.com/eda-benchmark/go-service/internal/kafka"
	"github.com/eda-benchmark/go-service/internal/metrics"
	"github.com/eda-benchmark/go-service/internal/pipeline"
	"github.com/eda-benchmark/go-service/internal/server"
)

func main() {
	os.Exit(run())
}

func run() int {
	cfg := config.Load()

	logger, err := zap.NewProduction()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to create logger: %v\n", err)
		return 1
	}
	defer logger.Sync() //nolint:errcheck

	rootCtx, cancel := context.WithCancel(context.Background())
	defer cancel()

	m := metrics.NewOrderMetrics()
	f := fault.New(cfg.FaultDelayMs, cfg.FaultFailRate)

	if err := kafka.WaitForKafka(rootCtx, cfg.KafkaBootstrap, logger); err != nil {
		logger.Fatal("kafka unreachable at startup", zap.Error(err))
	}

	producer, err := kafka.NewProducer(cfg.KafkaBootstrap, logger)
	if err != nil {
		logger.Fatal("failed to create kafka producer", zap.Error(err))
	}

	consumer := kafka.NewConsumer(cfg, producer, m, f, logger)
	go consumer.Start(rootCtx)

	dispatcher := pipeline.NewDispatcher(rootCtx, cfg.WorkerCount)
	eventHandler := pipeline.NewOrderPlacedHandler(m, logger)
	placeOrderHandler := pipeline.NewPlaceOrderHandler(
		cfg.TopicOrdersPlaced,
		producer,
		m, f, logger,
		eventHandler,
	)

	router := server.NewRouter(rootCtx, dispatcher, placeOrderHandler, m, logger)
	srv := server.New(cfg.HTTPPort, router, logger)

	go func() {
		if err := srv.Start(); err != nil {
			logger.Error("http server exited", zap.Error(err))
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
	sig := <-sigCh
	logger.Info("shutdown signal received", zap.String("signal", sig.String()))

	// 1. Stop accepting new HTTP requests; wait for in-flight handlers to finish
	httpCtx, httpCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer httpCancel()
	if err := srv.Shutdown(httpCtx); err != nil {
		logger.Error("http server shutdown error", zap.Error(err))
	}

	// 2. Cancel root context — stops consumer loop and dispatcher workers
	cancel()

	// 3. Drain in-flight order jobs (max 15 s)
	drainCtx, drainCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer drainCancel()
	if err := dispatcher.Shutdown(drainCtx); err != nil {
		logger.Error("dispatcher drain error", zap.Error(err))
	}

	// 4. Close Kafka clients
	if err := producer.Close(); err != nil {
		logger.Error("producer close error", zap.Error(err))
	}
	if err := consumer.Close(); err != nil {
		logger.Error("consumer close error", zap.Error(err))
	}

	logger.Info("shutdown complete")
	return 0
}
