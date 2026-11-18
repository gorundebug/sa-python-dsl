package functions

import (
	"context"
	"fmt"

	"example.com/redis-streams-events/eventprocessor/internal/types"

	datasourceredisstreams "github.com/gorundebug/servicelib/datasource/redisstreams"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type receiveEventSourceHandler = datasourceredisstreams.EndpointHandler[ReceiveEventSourceHandlerState, types.Event, types.PublicationOutcome, error]

var _ receiveEventSourceHandler = (*ReceiveEventSource)(nil)

func MakeEndpointConsumerReceiveEventSource(stream runtime.TypedInputStream[types.Event, types.PublicationOutcome, error], handler receiveEventSourceHandler) (runtime.Consumer[types.Event], error) {
	return datasourceredisstreams.MakeRedisStreamsEndpointConsumer[ReceiveEventSourceHandlerState, types.Event, types.PublicationOutcome, error](stream, handler)
}

type ReceiveEventSourceHandlerState struct {
}

type ReceiveEventSource struct{}

func (ep *ReceiveEventSource) OnError(ctx context.Context, sc datasourceredisstreams.StreamContext[types.Event, types.PublicationOutcome, error], err error) {
	if err != nil {
		sc.ErrorCollect(ctx, err)
	}
}

func (ep *ReceiveEventSource) BeginRequest(ctx context.Context, _ datasourceredisstreams.StreamContext[types.Event, types.PublicationOutcome, error]) (context.Context, ReceiveEventSourceHandlerState, error) {
	return ctx, ReceiveEventSourceHandlerState{}, nil
}

func (ep *ReceiveEventSource) ConsumeMessage(ctx context.Context, sc datasourceredisstreams.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveEventSourceHandlerState, msgData datasourceredisstreams.ConsumerMessage, resultCtx datasourceredisstreams.ResultContext[ReceiveEventSourceHandlerState, types.Event, types.PublicationOutcome, error]) error {
	id, idOK := msgData.Message.Values["ID"].(string)
	valueText, valueOK := msgData.Message.Values["Value"].(string)
	if !idOK || !valueOK {
		return fmt.Errorf("ID and Value must be string fields")
	}
	value := types.Event{ID: id, Value: valueText}
	if value.ID == "" {
		return fmt.Errorf("event ID is required")
	}
	// Register before Collect: a result can arrive synchronously.
	resultCtx.SetResultCallback(value.ID, func(resultCtxContext context.Context, sc datasourceredisstreams.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveEventSourceHandlerState, result types.PublicationOutcome) bool {
		// Done closes the request wait; settlement remains explicit below.
		defer resultCtx.Done()
		if result.Accepted {
			if err := msgData.Ack(resultCtxContext); err != nil {
				sc.ErrorCollect(resultCtxContext, err)
			}
		}

		return true
	})
	sc.Collect(ctx, value)
	return nil
}

func (ep *ReceiveEventSource) GetMessageID(_ context.Context, _ datasourceredisstreams.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveEventSourceHandlerState, value types.PublicationOutcome) string {
	return value.EventID
}

func (ep *ReceiveEventSource) EndRequest(_ context.Context, _ datasourceredisstreams.StreamContext[types.Event, types.PublicationOutcome, error], err error, _ ReceiveEventSourceHandlerState) {
}

func MakeReceiveEventSource(ctx context.Context, env environment.ServiceEnvironment) (*ReceiveEventSource, error) {
	return &ReceiveEventSource{}, nil
}
