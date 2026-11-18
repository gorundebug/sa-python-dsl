package functions

import (
	"context"
	"encoding/json"

	"example.com/nats-events/eventprocessor/internal/types"

	datasinknats "github.com/gorundebug/servicelib/datasink/nats"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type publishDurableEventSinkHandler = datasinknats.EndpointHandler[PublishDurableEventSinkHandlerState, types.Event, types.PublicationOutcome]

var _ publishDurableEventSinkHandler = (*PublishDurableEventSink)(nil)

// PublishDurableEventSinkHandlerState is created for each Consume call, even when stream IDs are equal.
type PublishDurableEventSinkHandlerState struct {
}

type PublishDurableEventSink struct{}

// OnError receives transport failures that cannot be attributed to a publish.
// Core disconnect/permission errors are not per-message delivery ACKs. Do not
// fabricate a result or request state here; implement explicit error policy.
func (ep *PublishDurableEventSink) OnError(ctx context.Context, stream runtime.Stream, err error) {
	if err != nil {
		stream.GetEnvironment().Log().Error(ctx, err.Error())
	}
}

// GetStreamID supplies correlation metadata; it does not group requests or state.
func (ep *PublishDurableEventSink) GetStreamID(ctx context.Context, value types.Event) string {
	if id, ok := runtime.StreamIdFromContext(ctx); ok {
		return id.GetID()
	}
	return value.ID
}

// BeginRequest runs for each input value. Preserve the supplied context.
// // Encode Event and publish through the native endpoint. Emit exactly one PublicationOutcome for each event, preserving
// EventID and the caller context. Use asynchronous publication with its callback; represent failed or unknown delivery
// as Accepted=false with a reason. Do not open a second broker client.
func (ep *PublishDurableEventSink) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, PublishDurableEventSinkHandlerState) {
	return ctx, PublishDurableEventSinkHandlerState{}
}

// ConsumeMessage serializes value into msg.Data and optional msg.Header.
// msg.Subject() is the configured publish subject. Choose an explicit operation:
//   - msg.Send(ctx, func(datasinknats.Delivery, error) types.PublicationOutcome): publish with delivery result callback; do not assume callback completion on return.
//   - msg.SendSync(ctx): returns (Delivery, error); call msg.Out(ctx, result) explicitly.
//   - msg.Skip(ctx, result): emit a result without publication.
//
// A successful JetStream publish returns Delivery.Ack with the server PubAck.
// This is publication acknowledgment, not confirmation of downstream processing.
// Results go to ordinary continuation output, separately from the declared error route.
// Return processing errors to EndRequest. Do not retain msg after this call.
func (ep *PublishDurableEventSink) ConsumeMessage(ctx context.Context, _ runtime.Stream, _ PublishDurableEventSinkHandlerState, value types.Event, msg *datasinknats.SinkMessage[types.PublicationOutcome]) error {
	data, err := json.Marshal(value)
	if err != nil {
		msg.Out(ctx, types.PublicationOutcome{EventID: value.ID, Reason: err.Error()})
		return nil
	}
	msg.Data = data
	msg.Send(ctx, func(delivery datasinknats.Delivery, err error) types.PublicationOutcome {
		result := types.PublicationOutcome{EventID: value.ID, Accepted: err == nil && delivery.Ack != nil}
		if err != nil {
			result.Reason = err.Error()
		}
		return result
	})
	return nil
}

// EndRequest runs when ConsumeMessage returns; asynchronous delivery callbacks may
// outlive it. Request completion is not delivery completion or source acknowledgement.
func (ep *PublishDurableEventSink) EndRequest(_ context.Context, _ runtime.Stream, err error, _ PublishDurableEventSinkHandlerState) {
	// Publication callback owns its copied input; this request owns no resources.
}

func MakePublishDurableEventSink(ctx context.Context, env environment.ServiceEnvironment) (*PublishDurableEventSink, error) {
	return &PublishDurableEventSink{}, nil
}
