package models

import (
	"fmt"
	"time"
)

// Order is the canonical order document exchanged between the HTTP layer,
// the pipeline, and Kafka topics. Mirrors the Order record in the .NET service.
type Order struct {
	OrderID    string      `json:"orderId"`
	CustomerID string      `json:"customerId"`
	Items      []OrderItem `json:"items"`
	Timestamp  time.Time   `json:"timestamp"`
}

// OrderItem is a single line item within an Order.
type OrderItem struct {
	SKU      string  `json:"sku"`
	Quantity int     `json:"quantity"`
	Price    float64 `json:"price"`
}

// Validate returns an error if any field violates business rules.
func (o *Order) Validate() error {
	if o.OrderID == "" {
		return fmt.Errorf("orderId is required")
	}
	if o.CustomerID == "" {
		return fmt.Errorf("customerId is required")
	}
	if len(o.Items) == 0 {
		return fmt.Errorf("items must contain at least one item")
	}
	for i, item := range o.Items {
		if item.SKU == "" {
			return fmt.Errorf("items[%d].sku is required", i)
		}
		if item.Quantity < 1 || item.Quantity > 1000 {
			return fmt.Errorf("items[%d].quantity must be between 1 and 1000", i)
		}
		if item.Price <= 0 {
			return fmt.Errorf("items[%d].price must be greater than 0", i)
		}
	}
	return nil
}
