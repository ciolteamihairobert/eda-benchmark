// .NET equivalent: PlaceOrderCommand / PlaceOrderResult records

package pipeline

import (
	"time"

	"github.com/eda-benchmark/go-service/internal/models"
)

// PlaceOrderCommand carries an incoming order through the pipeline.
type PlaceOrderCommand struct {
	Order *models.Order
}

// PlaceOrderResult is returned by PlaceOrderHandler on success.
type PlaceOrderResult struct {
	OrderID    string
	Status     string
	AcceptedAt time.Time
}
