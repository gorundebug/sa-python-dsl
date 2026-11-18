package functions

import (
	"context"
	"encoding/base64"
	"encoding/json"
	native "github.com/apache/pulsar-client-go/pulsar"

	"example.com/pulsar-events/eventprocessor/internal/types"

	datasinkpulsar "github.com/gorundebug/servicelib/datasink/pulsar"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type publishEventSinkHandler = datasinkpulsar.EndpointHandler[PublishEventSinkHandlerState, types.Event, types.PublicationOutcome]

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

func (ep *PublishEventSink) ConsumeMessage(ctx context.Context, _ runtime.Stream, _ PublishEventSinkHandlerState, value types.Event, msg *datasinkpulsar.SinkMessage[types.PublicationOutcome]) error {
	payload, err := json.Marshal(value)
	if err != nil {
		return err
	}
	msg.Message = native.ProducerMessage{Payload: payload, Key: value.ID}
	// Native callback can outlive EndRequest; capture only this value.
	msg.Send(ctx, func(delivery datasinkpulsar.Delivery, err error) types.PublicationOutcome {
		result := types.PublicationOutcome{EventID: value.ID, Accepted: err == nil && delivery.Outcome == datasinkpulsar.Accepted}
		if delivery.MessageID != nil {
			result.MessageID = base64.StdEncoding.EncodeToString(delivery.MessageID.Serialize())
		}
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
