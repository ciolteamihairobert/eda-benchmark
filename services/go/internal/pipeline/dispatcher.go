// Dispatcher is the in-process command dispatcher — the Go structural equivalent
// of MediatR's ISender/IPublisher in .NET. Commands are submitted via Dispatch()
// and executed by a fixed pool of worker goroutines, giving the same decoupling
// pattern as MediatR.Send() without reflection overhead.
//
// .NET equivalent: MediatR IMediator / ISender

package pipeline

import (
	"context"
	"errors"
	"fmt"
	"sync"
)

// ErrDispatcherFull is returned when the job queue is at capacity.
var ErrDispatcherFull = errors.New("dispatcher queue is full")

// ErrDispatcherClosed is returned when Dispatch is called after Shutdown.
var ErrDispatcherClosed = errors.New("dispatcher is closed")

type job struct {
	execute func() error
}

// Dispatcher routes work to a pool of goroutines via a buffered channel.
type Dispatcher struct {
	jobQueue     chan job
	wg           sync.WaitGroup
	workerCount  int
	shutdownCh   chan struct{}
	shutdownOnce sync.Once
}

// NewDispatcher starts workerCount goroutines and returns a ready Dispatcher.
// The provided ctx controls worker lifetime — workers exit when it is cancelled.
func NewDispatcher(ctx context.Context, workerCount int) *Dispatcher {
	d := &Dispatcher{
		jobQueue:    make(chan job, workerCount*10),
		workerCount: workerCount,
		shutdownCh:  make(chan struct{}),
	}
	for i := 0; i < workerCount; i++ {
		d.wg.Add(1)
		go d.runWorker(ctx)
	}
	return d
}

func (d *Dispatcher) runWorker(ctx context.Context) {
	defer d.wg.Done()
	for {
		select {
		case j, ok := <-d.jobQueue:
			if !ok {
				return
			}
			_ = j.execute()
		case <-ctx.Done():
			return
		}
	}
}

// Dispatch enqueues fn for execution by a worker goroutine. It is non-blocking:
// if the queue is full it returns ErrDispatcherFull immediately rather than waiting.
func (d *Dispatcher) Dispatch(ctx context.Context, fn func() error) error {
	select {
	case <-d.shutdownCh:
		return ErrDispatcherClosed
	default:
	}

	j := job{execute: fn}
	select {
	case d.jobQueue <- j:
		return nil
	case <-ctx.Done():
		return fmt.Errorf("dispatch cancelled: %w", ctx.Err())
	default:
		return ErrDispatcherFull
	}
}

// Shutdown signals the queue to stop accepting new work, then waits for all
// in-flight workers to finish. Returns an error if ctx expires first.
func (d *Dispatcher) Shutdown(ctx context.Context) error {
	d.shutdownOnce.Do(func() {
		close(d.shutdownCh)
		close(d.jobQueue)
	})

	done := make(chan struct{})
	go func() {
		d.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		return nil
	case <-ctx.Done():
		return fmt.Errorf("dispatcher shutdown timed out: %w", ctx.Err())
	}
}
