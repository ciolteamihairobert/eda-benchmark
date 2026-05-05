// .NET equivalent: FaultSettings + fault-injection logic in PlaceOrderHandler

package fault

import (
	"context"
	"errors"
	"math/rand"
	"time"
)

// ErrFaultInjected is returned when a random fault is triggered via FailRate.
var ErrFaultInjected = errors.New("fault injected")

// Fault encapsulates configurable chaos behaviour used to simulate degraded
// conditions during benchmark runs without redeploying the service.
type Fault struct {
	DelayMs  int
	FailRate float64
	rng      *rand.Rand
}

// New creates a Fault with a freshly seeded RNG.
func New(delayMs int, failRate float64) *Fault {
	return &Fault{
		DelayMs:  delayMs,
		FailRate: failRate,
		rng:      rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

// ShouldFail returns true with probability equal to FailRate.
func (f *Fault) ShouldFail() bool {
	if f.FailRate <= 0 {
		return false
	}
	return f.rng.Float64() < f.FailRate
}

// Sleep blocks for DelayMs milliseconds, or returns ctx.Err() if the context
// is cancelled before the delay elapses.
func (f *Fault) Sleep(ctx context.Context) error {
	if f.DelayMs <= 0 {
		return nil
	}
	select {
	case <-time.After(time.Duration(f.DelayMs) * time.Millisecond):
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}
