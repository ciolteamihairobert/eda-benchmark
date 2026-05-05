// .NET equivalent: OrderPlacedEvent : INotification

package pipeline

import (
	"time"

	"github.com/eda-benchmark/go-service/internal/models"
)

// OrderPlacedEvent is published in-process after an order is accepted,
// mirroring MediatR's INotification dispatch pattern.
type OrderPlacedEvent struct {
	Order      *models.Order
	AcceptedAt time.Time
}
