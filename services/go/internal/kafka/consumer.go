// .NET equivalent: KafkaConsumerService : BackgroundService

package kafka

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/segmentio/kafka-go"
	"go.uber.org/zap"

	"github.com/eda-benchmark/go-service/internal/config"
	"github.com/eda-benchmark/go-service/internal/fault"
	"github.com/eda-benchmark/go-service/internal/metrics"
	"github.com/eda-benchmark/go-service/internal/models"
)

// Consumer reads from orders.placed and routes messages to orders.processed
// or orders.failed, mirroring KafkaConsumerService in the .NET service.
type Consumer struct {
	reader   *kafka.Reader
	producer *Producer
	metrics  *metrics.OrderMetrics
	fault    *fault.Fault
	logger   *zap.Logger
	cfg      *config.Config
}

// NewConsumer creates a Consumer with manual-commit semantics for benchmark accuracy.
func NewConsumer(
	cfg *config.Config,
	producer *Producer,
	m *metrics.OrderMetrics,
	f *fault.Fault,
	logger *zap.Logger,
) *Consumer {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        []string{cfg.KafkaBootstrap},
		GroupID:        cfg.KafkaGroupID,
		Topic:          cfg.TopicOrdersPlaced,
		MinBytes:       1,
		MaxBytes:       10e6,
		CommitInterval: 0,
		StartOffset:    kafka.FirstOffset,
	})

	return &Consumer{
		reader:   reader,
		producer: producer,
		metrics:  m,
		fault:    f,
		logger:   logger,
		cfg:      cfg,
	}
}

// Start runs the consume loop in the calling goroutine until ctx is cancelled.
// Call via: go consumer.Start(ctx)
func (c *Consumer) Start(ctx context.Context) {
	c.logger.Info("consumer started", zap.String("topic", c.cfg.TopicOrdersPlaced))
	for {
		m, err := c.reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				break
			}
			c.logger.Error("fetch error", zap.Error(err))
			continue
		}
		if err := c.processMessage(ctx, m); err != nil {
			c.logger.Error("process error", zap.Error(err))
		}
	}
	c.logger.Info("consumer stopped")
}

// Close releases the reader connection.
func (c *Consumer) Close() error {
	if err := c.reader.Close(); err != nil {
		c.logger.Error("consumer close error", zap.Error(err))
		return fmt.Errorf("consumer close: %w", err)
	}
	c.logger.Info("kafka consumer closed")
	return nil
}

func (c *Consumer) processMessage(ctx context.Context, m kafka.Message) error {
	var order models.Order
	if err := json.Unmarshal(m.Value, &order); err != nil {
		c.logger.Error("unmarshal failed", zap.Error(err))
		_ = c.reader.CommitMessages(ctx, m)
		c.metrics.OrdersFailed.WithLabelValues("deserialization").Inc()
		return nil
	}

	c.logger.Debug("processing order",
		zap.String("orderId", order.OrderID),
		zap.Int("partition", m.Partition),
		zap.Int64("offset", m.Offset),
	)

	if err := c.fault.Sleep(ctx); err != nil {
		return fmt.Errorf("fault sleep: %w", err)
	}

	payload, _ := json.Marshal(order)

	if err := c.producer.Produce(ctx, c.cfg.TopicOrdersProcessed, order.OrderID, string(payload)); err != nil {
		c.logger.Error("failed to produce to processed topic",
			zap.String("orderId", order.OrderID),
			zap.Error(err),
		)
		_ = c.producer.Produce(ctx, c.cfg.TopicOrdersFailed, order.OrderID, string(payload))
		_ = c.reader.CommitMessages(ctx, m)
		c.metrics.OrdersFailed.WithLabelValues("processing").Inc()
		return nil
	}

	_ = c.reader.CommitMessages(ctx, m)
	c.metrics.OrdersProcessed.Inc()
	return nil
}
