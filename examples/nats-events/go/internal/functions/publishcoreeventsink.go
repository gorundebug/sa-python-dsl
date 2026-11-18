package functions

import (
	"context"
	"encoding/json"

	"example.com/nats-events/eventprocessor/internal/types"

	datasinknats "github.com/gorundebug/servicelib/datasink/nats"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type publishCoreEventSinkHandler = datasinknats.EndpointHandler[PublishCoreEventSinkHandlerState, types.Event, types.PublicationOutcome]

var _ publishCoreEventSinkHandler = (*PublishCoreEventSink)(nil)

// PublishCoreEventSinkHandlerState is created for each Consume call, even when stream IDs are equal.
type PublishCoreEventSinkHandlerState struct {
}

type PublishCoreEventSink struct{}

// OnError receives transport failures that cannot be attributed to a publish.
// Core disconnect/permission errors are not per-message delivery ACKs. Do not
// fabricate a result or request state here; implement explicit error policy.
func (ep *PublishCoreEventSink) OnError(ctx context.Context, stream runtime.Stream, err error) {
	if err != nil {
		stream.GetEnvironment().Log().Error(ctx, err.Error())
	}
}

// GetStreamID supplies correlation metadata; it does not group requests or state.
func (ep *PublishCoreEventSink) GetStreamID(ctx context.Context, value types.Event) string {
	if id, ok := runtime.StreamIdFromContext(ctx); ok {
		return id.GetID()
	}
	return value.ID
}

// BeginRequest runs for each input value. Preserve the supplied context.
// // Encode Event and publish through the native endpoint. Emit exactly one PublicationOutcome for each event, preserving
// EventID and the caller context. Use asynchronous publication with its callback; represent failed or unknown delivery
// as Accepted=false with a reason. Do not open a second broker client.
func (ep *PublishCoreEventSink) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, PublishCoreEventSinkHandlerState) {
	return ctx, PublishCoreEventSinkHandlerState{}
}

// ConsumeMessage serializes value into msg.Data and optional msg.Header.
// msg.Subject() is the configured publish subject. Choose an explicit operation:
//   - msg.Send(ctx, func(datasinknats.Delivery, error) types.PublicationOutcome): publish with delivery result callback; do not assume callback completion on return.
//   - msg.SendSync(ctx): returns (Delivery, error); call msg.Out(ctx, result) explicitly.
//   - msg.Skip(ctx, result): emit a result without publication.
//
// Core Send reports local acceptance only; SendSync explicitly waits for a
// protocol flush. Delivery.Ack is nil; neither confirms subscriber delivery.
// Results go to ordinary continuation output, separately from the declared error route.
// Return processing errors to EndRequest. Do not retain msg after this call.
func (ep *PublishCoreEventSink) ConsumeMessage(ctx context.Context, _ runtime.Stream, _ PublishCoreEventSinkHandlerState, value types.Event, msg *datasinknats.SinkMessage[types.PublicationOutcome]) error {
	data, err := json.Marshal(value)
	if err != nil {
		msg.Out(ctx, types.PublicationOutcome{EventID: value.ID, Reason: err.Error()})
		return nil
	}
	msg.Data = data
	msg.Send(ctx, func(delivery datasinknats.Delivery, err error) types.PublicationOutcome {
		result := types.PublicationOutcome{EventID: value.ID, Accepted: err == nil && delivery.Accepted}
		if err != nil {
			result.Reason = err.Error()
		}
		return result
	})
	return nil
}

// EndRequest runs when ConsumeMessage returns; asynchronous delivery callbacks may
// outlive it. Request completion is not delivery completion or source acknowledgement.
func (ep *PublishCoreEventSink) EndRequest(_ context.Context, _ runtime.Stream, err error, _ PublishCoreEventSinkHandlerState) {
	// Publication callback owns its copied input; this request owns no resources.
}

func MakePublishCoreEventSink(ctx context.Context, env environment.ServiceEnvironment) (*PublishCoreEventSink, error) {
	return &PublishCoreEventSink{}, nil
}
