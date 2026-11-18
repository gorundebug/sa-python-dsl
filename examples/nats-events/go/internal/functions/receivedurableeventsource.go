package functions

import (
	"context"
	"encoding/json"
	"fmt"

	"example.com/nats-events/eventprocessor/internal/types"

	datasourcenats "github.com/gorundebug/servicelib/datasource/nats"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type receiveDurableEventSourceHandler = datasourcenats.EndpointHandler[ReceiveDurableEventSourceHandlerState, types.Event, types.PublicationOutcome, error]

var _ receiveDurableEventSourceHandler = (*ReceiveDurableEventSource)(nil)

func MakeEndpointConsumerReceiveDurableEventSource(stream runtime.TypedInputStream[types.Event, types.PublicationOutcome, error], handler receiveDurableEventSourceHandler) (runtime.Consumer[types.Event], error) {
	return datasourcenats.MakeNATSEndpointConsumer[ReceiveDurableEventSourceHandlerState, types.Event, types.PublicationOutcome, error](stream, handler)
}

// ReceiveDurableEventSourceHandlerState belongs to one delivery. Result callbacks may run concurrently with
// ConsumeMessage and each other; synchronize shared state accessed by callbacks.
type ReceiveDurableEventSourceHandlerState struct {
}

type ReceiveDurableEventSource struct{}

// OnError receives transport failures without per-message state. Map failures
// explicitly to the declared error type; this does not ACK or retry a delivery.
func (ep *ReceiveDurableEventSource) OnError(ctx context.Context, sc datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], err error) {
	if err != nil {
		sc.ErrorCollect(ctx, err)
	}
}

// BeginRequest runs once per delivery. Preserve ctx. On failure, release any
// acquired resources here: ConsumeMessage and EndRequest will not be called.
// // Decode Event from native message bytes. Register the result callback before Collect; keep the supplied context and
// correlate by Event.ID. On outcome, ACK only a confirmed successful publication; NAK publication failures. A missing
// ACK can cause redelivery; processing must be idempotent. Call Done after handling the outcome. Done itself never
// ACKs.
func (ep *ReceiveDurableEventSource) BeginRequest(ctx context.Context, _ datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error]) (context.Context, ReceiveDurableEventSourceHandlerState, error) {
	return ctx, ReceiveDurableEventSourceHandlerState{}, nil
}

// ConsumeMessage receives native subject, reply, headers and bytes in msgData.Message.
// Register result callbacks BEFORE sc.Collect: the graph may return synchronously.
// Call resultCtx.Done only when this request's processing is complete. Done is not ACK.
// JetStream requires explicit msgData.JetStream.Ack() or DoubleAck(ctx) after the
// required work is durable. Nak()/NakWithDelay select redelivery explicitly.
// Unacked deliveries may recur; implement idempotent processing. Do not ACK a
// failed request merely because EndRequest or an error collector was called.
// The native source processes one request at a time per endpoint. Keep handlers
// cancellation-aware; do not add a detached consumer or private dispatcher.
func (ep *ReceiveDurableEventSource) ConsumeMessage(ctx context.Context, sc datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveDurableEventSourceHandlerState, msgData datasourcenats.ConsumerMessage, resultCtx datasourcenats.ResultContext[ReceiveDurableEventSourceHandlerState, types.Event, types.PublicationOutcome, error]) error {
	var value types.Event
	if err := json.Unmarshal(msgData.Message.Data, &value); err != nil {
		return err
	}
	if value.ID == "" {
		return fmt.Errorf("event ID is required")
	}
	resultCtx.SetResultCallback(value.ID, func(resultCtxContext context.Context, sc datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveDurableEventSourceHandlerState, result types.PublicationOutcome) bool {
		defer resultCtx.Done()
		if result.Accepted {
			if err := msgData.JetStream.DoubleAck(resultCtxContext); err != nil {
				sc.ErrorCollect(resultCtxContext, err)
			}
		} else {
			if err := msgData.JetStream.Nak(); err != nil {
				sc.ErrorCollect(resultCtxContext, err)
			}
		}
		return true
	})
	sc.Collect(ctx, value)
	return nil
}

// GetMessageID correlates a pipeline result with the registered result callback.
func (ep *ReceiveDurableEventSource) GetMessageID(_ context.Context, _ datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveDurableEventSourceHandlerState, value types.PublicationOutcome) string {
	return value.EventID
}

// EndRequest runs after processing/result completion, error, or cancellation;
// accepted result callbacks finish before finalization. Release owned resources.
func (ep *ReceiveDurableEventSource) EndRequest(_ context.Context, _ datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], err error, _ ReceiveDurableEventSourceHandlerState) {
	// No delivery-owned resources; failure leaves a JetStream message unacknowledged.
}

// MakeReceiveDurableEventSource constructs the native jetstream source handler once at startup.
func MakeReceiveDurableEventSource(ctx context.Context, env environment.ServiceEnvironment) (*ReceiveDurableEventSource, error) {
	return &ReceiveDurableEventSource{}, nil
}
