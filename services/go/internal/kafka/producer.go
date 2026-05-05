// .NET equivalent: KafkaProducerService : BackgroundService

package kafka

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/segmentio/kafka-go"
	"go.uber.org/zap"
)

// Producer wraps a kafka-go Writer and exposes a simple Produce method.
type Producer struct {
	writer *kafka.Writer
	logger *zap.Logger
}

// NewProducer dials the broker to verify connectivity, then creates a Writer.
// Returns an error if the broker is unreachable.
func NewProducer(bootstrap string, logger *zap.Logger) (*Producer, error) {
	conn, err := kafka.DialContext(context.Background(), "tcp", bootstrap)
	if err != nil {
		return nil, fmt.Errorf("kafka dial %s: %w", bootstrap, err)
	}
	conn.Close()

	w := &kafka.Writer{
		Addr:         kafka.TCP(bootstrap),
		Balancer:     &kafka.LeastBytes{},
		RequiredAcks: kafka.RequireAll,
		MaxAttempts:  3,
		BatchTimeout: 10 * time.Millisecond,
		Async:        false,
	}

	logger.Info("kafka producer ready", zap.String("bootstrap", bootstrap))
	return &Producer{writer: w, logger: logger}, nil
}

// WaitForKafka retries dialing the broker every 5 seconds for up to 12 attempts.
// It is intended to be called from main during startup before creating a Producer.
func WaitForKafka(ctx context.Context, bootstrap string, logger *zap.Logger) error {
	for attempt := 1; attempt <= 12; attempt++ {
		conn, err := kafka.DialContext(ctx, "tcp", bootstrap)
		if err == nil {
			conn.Close()
			logger.Info("kafka reachable", zap.String("bootstrap", bootstrap))
			return nil
		}
		logger.Warn("kafka not ready, retrying",
			zap.Int("attempt", attempt),
			zap.String("bootstrap", bootstrap),
			zap.Error(err),
		)
		select {
		case <-time.After(5 * time.Second):
		case <-ctx.Done():
			return fmt.Errorf("context cancelled while waiting for kafka: %w", ctx.Err())
		}
	}
	return errors.New("kafka not reachable after 12 attempts")
}

// Produce writes a single message to the given topic synchronously.
func (p *Producer) Produce(ctx context.Context, topic, key, value string) error {
	msg := kafka.Message{
		Topic: topic,
		Key:   []byte(key),
		Value: []byte(value),
	}
	if err := p.writer.WriteMessages(ctx, msg); err != nil {
		p.logger.Error("produce failed",
			zap.String("topic", topic),
			zap.String("key", key),
			zap.Error(err),
		)
		return fmt.Errorf("write message topic=%s key=%s: %w", topic, key, err)
	}
	p.logger.Debug("message produced",
		zap.String("topic", topic),
		zap.String("key", key),
	)
	return nil
}

// Close flushes pending writes and releases the underlying connection.
func (p *Producer) Close() error {
	if err := p.writer.Close(); err != nil {
		p.logger.Error("producer close error", zap.Error(err))
		return fmt.Errorf("producer close: %w", err)
	}
	p.logger.Info("kafka producer closed")
	return nil
}
