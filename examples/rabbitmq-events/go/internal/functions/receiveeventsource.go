package functions

import (
	"context"
	"encoding/json"
	"fmt"

	"example.com/rabbitmq-events/eventprocessor/internal/types"

	datasourcerabbitmq "github.com/gorundebug/servicelib/datasource/rabbitmq"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type receiveEventSourceHandler = datasourcerabbitmq.EndpointHandler[ReceiveEventSourceHandlerState, types.Event, types.PublicationOutcome, error]

var _ receiveEventSourceHandler = (*ReceiveEventSource)(nil)

func MakeEndpointConsumerReceiveEventSource(stream runtime.TypedInputStream[types.Event, types.PublicationOutcome, error], handler receiveEventSourceHandler) (runtime.Consumer[types.Event], error) {
	return datasourcerabbitmq.MakeRabbitMQEndpointConsumer[ReceiveEventSourceHandlerState, types.Event, types.PublicationOutcome, error](stream, handler)
}

type ReceiveEventSourceHandlerState struct {
}

type ReceiveEventSource struct{}

func (ep *ReceiveEventSource) OnError(ctx context.Context, sc datasourcerabbitmq.StreamContext[types.Event, types.PublicationOutcome, error], err error) {
	if err != nil {
		sc.ErrorCollect(ctx, err)
	}
}

func (ep *ReceiveEventSource) BeginRequest(ctx context.Context, _ datasourcerabbitmq.StreamContext[types.Event, types.PublicationOutcome, error]) (context.Context, ReceiveEventSourceHandlerState, error) {
	return ctx, ReceiveEventSourceHandlerState{}, nil
}

func (ep *ReceiveEventSource) ConsumeMessage(ctx context.Context, sc datasourcerabbitmq.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveEventSourceHandlerState, msgData datasourcerabbitmq.ConsumerMessage, resultCtx datasourcerabbitmq.ResultContext[ReceiveEventSourceHandlerState, types.Event, types.PublicationOutcome, error]) error {
	var value types.Event
	// Official clients may encode JSON bytes as either AMQP Data or a binary
	// Value section. Preserve that native representation in the SDK and decode
	// the application payload here.
	payload := msgData.Message.GetData()
	if len(msgData.Message.Data) == 0 {
		switch body := msgData.Message.Value.(type) {
		case []byte:
			payload = body
		case string:
			payload = []byte(body)
		default:
			return fmt.Errorf("Event requires AMQP Data or a binary/string Value, got %T", body)
		}
	}
	if err := json.Unmarshal(payload, &value); err != nil {
		return err
	}
	if value.ID == "" {
		return fmt.Errorf("event ID is required")
	}
	// Register before Collect: a result can arrive synchronously.
	resultCtx.SetResultCallback(value.ID, func(resultCtxContext context.Context, sc datasourcerabbitmq.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveEventSourceHandlerState, result types.PublicationOutcome) bool {
		// Done closes the request wait; settlement remains explicit below.
		defer resultCtx.Done()
		if result.Accepted {
			if err := msgData.Accept(resultCtxContext); err != nil {
				sc.ErrorCollect(resultCtxContext, err)
			}
		} else {
			if err := msgData.Release(resultCtxContext); err != nil {
				sc.ErrorCollect(resultCtxContext, err)
			}
		}
		return true
	})
	sc.Collect(ctx, value)
	return nil
}

func (ep *ReceiveEventSource) GetMessageID(_ context.Context, _ datasourcerabbitmq.StreamContext[types.Event, types.PublicationOutcome, error], _ ReceiveEventSourceHandlerState, value types.PublicationOutcome) string {
	return value.EventID
}

func (ep *ReceiveEventSource) EndRequest(_ context.Context, _ datasourcerabbitmq.StreamContext[types.Event, types.PublicationOutcome, error], err error, _ ReceiveEventSourceHandlerState) {
}

func MakeReceiveEventSource(ctx context.Context, env environment.ServiceEnvironment) (*ReceiveEventSource, error) {
	return &ReceiveEventSource{}, nil
}
