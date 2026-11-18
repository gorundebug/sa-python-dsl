package functions

import (
	"context"

	"example.com/redis-streams-events/eventprocessor/internal/types"

	datasinkredisstreams "github.com/gorundebug/servicelib/datasink/redisstreams"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type publishEventSinkHandler = datasinkredisstreams.EndpointHandler[PublishEventSinkHandlerState, types.Event, types.PublicationOutcome]

var _ publishEventSinkHandler = (*PublishEventSink)(nil)

type PublishEventSinkHandlerState struct {
}

type PublishEventSink struct{}

func (ep *PublishEventSink) OnError(ctx context.Context, stream runtime.Stream, err error) {
	if err != nil {
		stream.GetEnvironment().Log().Error(ctx, err.Error())
	}
}

func (ep *PublishEventSink) GetStreamID(ctx context.Context, value types.Event) string {
	if id, ok := runtime.StreamIdFromContext(ctx); ok {
		return id.GetID()
	}
	return value.ID
}

func (ep *PublishEventSink) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, PublishEventSinkHandlerState) {
	return ctx, PublishEventSinkHandlerState{}
}

func (ep *PublishEventSink) ConsumeMessage(ctx context.Context, _ runtime.Stream, _ PublishEventSinkHandlerState, value types.Event, msg *datasinkredisstreams.SinkMessage[types.PublicationOutcome]) error {
	msg.Fields = []datasinkredisstreams.Field{{Name: "ID", Value: value.ID}, {Name: "Value", Value: value.Value}}
	// Native callback can outlive EndRequest; capture only this value.
	msg.Send(ctx, func(delivery datasinkredisstreams.Delivery, err error) types.PublicationOutcome {
		result := types.PublicationOutcome{EventID: value.ID, EntryID: delivery.EntryID, Accepted: err == nil && delivery.Outcome == datasinkredisstreams.Accepted}
		if err != nil {
			result.Reason = err.Error()
		}
		if !result.Accepted && result.Reason == "" {
			result.Reason = string(delivery.Outcome)
		}
		return result
	})
	return nil
}

func (ep *PublishEventSink) EndRequest(_ context.Context, _ runtime.Stream, err error, _ PublishEventSinkHandlerState) {
}

func MakePublishEventSink(ctx context.Context, env environment.ServiceEnvironment) (*PublishEventSink, error) {
	return &PublishEventSink{}, nil
}
