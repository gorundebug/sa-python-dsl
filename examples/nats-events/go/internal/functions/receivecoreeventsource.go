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

type receiveCoreEventSourceHandler = datasourcenats.EndpointHandler[ReceiveCoreEventSourceHandlerState, types.Event, types.PublicationOutcome, error]

var _ receiveCoreEventSourceHandler = (*ReceiveCoreEventSource)(nil)

func MakeEndpointConsumerReceiveCoreEventSource(stream runtime.TypedInputStream[types.Event, types.PublicationOutcome, error], handler receiveCoreEventSourceHandler) (runtime.Consumer[types.Event], error) {
	return datasourcenats.MakeNATSEndpointConsumer[ReceiveCoreEventSourceHandlerState, types.Event, types.PublicationOutcome, error](stream, handler)
}

// ReceiveCoreEventSourceHandlerState belongs to one delivery. Result callbacks may run concurrently with
// ConsumeMessage and each other; synchronize shared state accessed by callbacks.
type ReceiveCoreEventSourceHandlerState struct {
}

type ReceiveCoreEventSource struct{}

// OnError receives transport failures without per-message state. Map failures
// explicitly to the declared error type; this does not ACK or retry a delivery.
func (ep *ReceiveCoreEventSource) OnError(ctx context.Context, sc datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], err error) {
	if err != nil {
		sc.ErrorCollect(ctx, err)
	}
}

// BeginRequest runs once per delivery. Preserve ctx. On failure, release any
// acquired resources here: ConsumeMessage and EndRequest will not be called.
// // Decode Event from native message bytes. Register the result callback before Collect; keep the supplied context and
// correlate by Event.ID. On outcome, record local publication acceptance or failure; Core has no ACK or replay. Call
// Done after handling the outcome. Done itself never ACKs.
func (ep *ReceiveCoreEventSource) BeginRequest(ctx context.Context, _ datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error]) (context.Context, ReceiveCoreEventSourceHandlerState, error) {
	return ctx, ReceiveCoreEventSourceHandlerState{}, nil
}

// ConsumeMessage receives native subject, reply, headers and bytes in msgData.Message.
// Register result callbacks BEFORE sc.Collect: the graph may return synchronously.
// Call resultCtx.Done only when this request's processing is complete. Done is not ACK.
// Core NATS has no broker ACK, durable replay, or automatic redelivery. The
// msgData.JetStream field is nil. Do not call JetStream acknowledgment methods.
// The native source processes one request at a time per endpoint. Keep handlers
// cancellation-aware; do not add a detached consumer or private dispatcher.
func (ep *ReceiveCoreEventSource) ConsumeMessage(ctx context.Context, sc datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveCoreEventSourceHandlerState, msgData datasourcenats.ConsumerMessage, resultCtx datasourcenats.ResultContext[ReceiveCoreEventSourceHandlerState, types.Event, types.PublicationOutcome, error]) error {
	var value types.Event
	if err := json.Unmarshal(msgData.Message.Data, &value); err != nil {
		return err
	}
	if value.ID == "" {
		return fmt.Errorf("event ID is required")
	}
	resultCtx.SetResultCallback(value.ID, func(resultCtxContext context.Context, sc datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveCoreEventSourceHandlerState, result types.PublicationOutcome) bool {
		defer resultCtx.Done()
		if !result.Accepted {
			sc.ErrorCollect(resultCtxContext, fmt.Errorf("publication failed: %s", result.Reason))
		}
		return true
	})
	sc.Collect(ctx, value)
	return nil
}

// GetMessageID correlates a pipeline result with the registered result callback.
func (ep *ReceiveCoreEventSource) GetMessageID(_ context.Context, _ datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveCoreEventSourceHandlerState, value types.PublicationOutcome) string {
	return value.EventID
}

// EndRequest runs after processing/result completion, error, or cancellation;
// accepted result callbacks finish before finalization. Release owned resources.
func (ep *ReceiveCoreEventSource) EndRequest(_ context.Context, _ datasourcenats.StreamContext[types.Event, types.PublicationOutcome, error], err error, _ ReceiveCoreEventSourceHandlerState) {
	// No delivery-owned resources; failure leaves a JetStream message unacknowledged.
}

// MakeReceiveCoreEventSource constructs the native nats source handler once at startup.
func MakeReceiveCoreEventSource(ctx context.Context, env environment.ServiceEnvironment) (*ReceiveCoreEventSource, error) {
	return &ReceiveCoreEventSource{}, nil
}
