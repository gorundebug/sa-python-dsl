package functions

import (
	"context"
	"encoding/json"
	"fmt"

	"example.com/pulsar-events/eventprocessor/internal/types"

	datasourcepulsar "github.com/gorundebug/servicelib/datasource/pulsar"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type receiveEventSourceHandler = datasourcepulsar.EndpointHandler[ReceiveEventSourceHandlerState, types.Event, types.PublicationOutcome, error]

var _ receiveEventSourceHandler = (*ReceiveEventSource)(nil)

func MakeEndpointConsumerReceiveEventSource(stream runtime.TypedInputStream[types.Event, types.PublicationOutcome, error], handler receiveEventSourceHandler) (runtime.Consumer[types.Event], error) {
	return datasourcepulsar.MakePulsarEndpointConsumer[ReceiveEventSourceHandlerState, types.Event, types.PublicationOutcome, error](stream, handler)
}

type ReceiveEventSourceHandlerState struct {
}

type ReceiveEventSource struct{}

func (ep *ReceiveEventSource) OnError(ctx context.Context, sc datasourcepulsar.StreamContext[types.Event, types.PublicationOutcome, error], err error) {
	if err != nil {
		sc.ErrorCollect(ctx, err)
	}
}

func (ep *ReceiveEventSource) BeginRequest(ctx context.Context, _ datasourcepulsar.StreamContext[types.Event, types.PublicationOutcome, error]) (context.Context, ReceiveEventSourceHandlerState, error) {
	return ctx, ReceiveEventSourceHandlerState{}, nil
}

func (ep *ReceiveEventSource) ConsumeMessage(ctx context.Context, sc datasourcepulsar.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveEventSourceHandlerState, msgData datasourcepulsar.ConsumerMessage, resultCtx datasourcepulsar.ResultContext[ReceiveEventSourceHandlerState, types.Event, types.PublicationOutcome, error]) error {
	var value types.Event
	if err := json.Unmarshal(msgData.Message.Payload(), &value); err != nil {
		return err
	}
	if value.ID == "" {
		return fmt.Errorf("event ID is required")
	}
	// Register before Collect: a result can arrive synchronously.
	resultCtx.SetResultCallback(value.ID, func(resultCtxContext context.Context, sc datasourcepulsar.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveEventSourceHandlerState, result types.PublicationOutcome) bool {
		// Done closes the request wait; settlement remains explicit below.
		defer resultCtx.Done()
		if result.Accepted && result.MessageID != "" {
			if err := msgData.Ack(resultCtxContext); err != nil {
				sc.ErrorCollect(resultCtxContext, err)
			}
		}

		return true
	})
	sc.Collect(ctx, value)
	return nil
}

func (ep *ReceiveEventSource) GetMessageID(_ context.Context, _ datasourcepulsar.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveEventSourceHandlerState, value types.PublicationOutcome) string {
	return value.EventID
}

func (ep *ReceiveEventSource) EndRequest(_ context.Context, _ datasourcepulsar.StreamContext[types.Event, types.PublicationOutcome, error], err error, _ ReceiveEventSourceHandlerState) {
}

func MakeReceiveEventSource(ctx context.Context, env environment.ServiceEnvironment) (*ReceiveEventSource, error) {
	return &ReceiveEventSource{}, nil
}
