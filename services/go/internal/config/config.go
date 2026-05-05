package config

import (
	"fmt"
	"os"
	"strconv"
)

// Config holds all runtime configuration read from environment variables.
type Config struct {
	KafkaBootstrap       string
	KafkaGroupID         string
	TopicOrdersPlaced    string
	TopicOrdersProcessed string
	TopicOrdersFailed    string
	HTTPPort             string
	FaultDelayMs         int
	FaultFailRate        float64
	WorkerCount          int
}

// Load reads configuration from environment variables, falling back to defaults.
func Load() *Config {
	cfg := &Config{
		KafkaBootstrap:       getEnvOrDefault("KAFKA_BOOTSTRAP", "localhost:9092"),
		KafkaGroupID:         getEnvOrDefault("KAFKA_GROUP_ID", "go-order-service"),
		TopicOrdersPlaced:    getEnvOrDefault("TOPIC_PLACED", "orders.placed"),
		TopicOrdersProcessed: getEnvOrDefault("TOPIC_PROCESSED", "orders.processed"),
		TopicOrdersFailed:    getEnvOrDefault("TOPIC_FAILED", "orders.failed"),
		HTTPPort:             getEnvOrDefault("HTTP_PORT", "8081"),
		FaultDelayMs:         0,
		FaultFailRate:        0.0,
		WorkerCount:          10,
	}

	if v := os.Getenv("FAULT_DELAY_MS"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			fmt.Fprintf(os.Stderr, "warn: FAULT_DELAY_MS=%q is not an integer, using default 0\n", v)
		} else {
			cfg.FaultDelayMs = n
		}
	}

	if v := os.Getenv("FAULT_FAIL_RATE"); v != "" {
		f, err := strconv.ParseFloat(v, 64)
		if err != nil {
			fmt.Fprintf(os.Stderr, "warn: FAULT_FAIL_RATE=%q is not a float, using default 0.0\n", v)
		} else {
			cfg.FaultFailRate = f
		}
	}

	if v := os.Getenv("WORKER_COUNT"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			fmt.Fprintf(os.Stderr, "warn: WORKER_COUNT=%q is not an integer, using default 10\n", v)
		} else {
			cfg.WorkerCount = n
		}
	}

	return cfg
}

func getEnvOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
