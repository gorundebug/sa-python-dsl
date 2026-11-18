package app

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"testing"
	"time"

	"example.com/rabbitmq-events/eventprocessor/internal/config"
	"example.com/rabbitmq-events/eventprocessor/internal/types"
	"github.com/Azure/go-amqp"
	"github.com/gorundebug/servicelib/runtime"
	rmq "github.com/rabbitmq/rabbitmq-amqp-go-client/pkg/rabbitmqamqp"
)

// Runs the generated service graph against an existing RabbitMQ 4.x broker.
// Only the uniquely named resources created by this test are removed.
func TestCanonicalRabbitMQEventPipelines(t *testing.T) {
	address := os.Getenv("RABBITMQ_TEST_URL")
	if address == "" {
		t.Skip("set RABBITMQ_TEST_URL")
	}
	user, pass := os.Getenv("RABBITMQ_TEST_USERNAME"), os.Getenv("RABBITMQ_TEST_PASSWORD")
	if user == "" {
		user = "adapter"
		pass = "adapter-test"
	}
	ctx, cancel := context.WithTimeout(t.Context(), 30*time.Second)
	defer cancel()
	client, err := rmq.Dial(ctx, address, &rmq.AmqpConnOptions{SASLType: amqp.SASLTypePlain(user, pass), RecoveryConfiguration: &rmq.RecoveryConfiguration{ActiveRecovery: false}, TopologyRecoveryOptions: rmq.TopologyRecoveryDisabled})
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		stop, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		client.Close(stop)
	}()
	suffix := runtime.NewStreamID()
	incoming := "example.in." + suffix
	processed := "example.out." + suffix
	exchange := "example.events." + suffix
	defer func() {
		cleanup, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		client.Management().DeleteQueue(cleanup, incoming)
		client.Management().DeleteQueue(cleanup, processed)
		client.Management().DeleteExchange(cleanup, exchange)
	}()
	for _, name := range []string{"SERVICELIB_NOOP_METRICS", "SERVICELIB_NOOP_LOGS", "SERVICELIB_NOOP_TRACING"} {
		t.Setenv(name, "1")
	}
	for name, value := range map[string]string{"EVENTS_SERVERS": address, "EVENTS_USERNAME": user, "EVENTS_PASSWORD": pass, "RECEIVE_EVENT_QUEUE_NAME": incoming, "PUBLISH_EVENT_QUEUE_NAME": processed, "PUBLISH_EVENT_EXCHANGE_NAME": exchange, "EVENT_PROCESSOR_HTTP_PORT": "0", "EVENT_PROCESSOR_GRPC_PORT": "0"} {
		t.Setenv(name, value)
	}
	// These assertions exercise generated environment wiring, not direct config mutation.
	configured := config.MakeConfig()
	if err := configured.ApplyEnvironment(); err != nil {
		t.Fatal(err)
	}
	if configured.DataConnectors.Events.Username != user || configured.DataConnectors.Events.Password != pass {
		t.Fatal("generated RabbitMQ environment overrides omit runtime-only username/password")
	}
	if configured.Endpoints.ReceiveEvent.QueueName != incoming || configured.Endpoints.PublishEvent.QueueName != processed || configured.Endpoints.PublishEvent.ExchangeName != exchange {
		t.Fatal("generated endpoint environment overrides lost")
	}
	service, err := runtime.MakeService[*Service, *config.Config](ctx, "EventProcessor", &serviceDependencies{}, nil, nil, func() *Service { return &Service{} }, config.MakeConfig)
	if err != nil {
		t.Fatal(err)
	}
	defer service.Release(ctx)
	if err = service.StartService(ctx); err != nil {
		t.Fatal(err)
	}
	stopped := false
	defer func() {
		if !stopped {
			stop, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			defer cancel()
			service.StopService(stop)
		}
	}()
	for _, record := range []any{types.Event{ID: "serde", Value: "record"}, types.PublicationOutcome{EventID: "serde", Accepted: true}} {
		codec, e := service.GetSerde(reflect.TypeOf(record))
		if e != nil || codec == nil {
			t.Fatalf("serializer: %v", e)
		}
		encoded, e := codec.SerializeObj(record, nil)
		if e != nil {
			t.Fatal(e)
		}
		decoded, e := codec.DeserializeObj(encoded)
		if e != nil || !reflect.DeepEqual(record, decoded) {
			t.Fatalf("serde roundtrip: %+v %v", decoded, e)
		}
	}
	publisher, err := client.NewPublisher(ctx, &rmq.QueueAddress{Queue: incoming}, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer publisher.Close(ctx)
	consumer, err := client.NewConsumer(ctx, processed, &rmq.ConsumerOptions{InitialCredits: 1, SettleStrategy: rmq.ExplicitSettle})
	if err != nil {
		t.Fatal(err)
	}
	defer consumer.Close(ctx)
	const count = 3
	for i := 0; i < count; i++ {
		id := fmt.Sprintf("event-%d", i)
		payload, _ := json.Marshal(types.Event{ID: id, Value: " hello "})
		message := rmq.NewMessage(payload)
		message.ApplicationProperties = map[string]any{"X-Stream-ID": "trace-" + id}
		result, e := publisher.Publish(ctx, message)
		if e != nil {
			t.Fatal(e)
		}
		if _, ok := result.Outcome.(*rmq.StateAccepted); !ok {
			t.Fatalf("input not accepted: %T", result.Outcome)
		}
		output, e := consumer.Receive(ctx)
		if e != nil {
			t.Fatal(e)
		}
		var event types.Event
		if e = json.Unmarshal(output.Message().GetData(), &event); e != nil {
			t.Fatal(e)
		}
		if event.ID != id || event.Value != "HELLO" {
			t.Fatalf("unexpected processed event: %+v", event)
		}
		if output.Message().ApplicationProperties["x-stream-id"] != "trace-"+id {
			t.Fatal("correlation lost across generated pipeline")
		}
		if e = output.Accept(ctx); e != nil {
			t.Fatal(e)
		}
	}
	stop, stopCancel := context.WithTimeout(ctx, 3*time.Second)
	defer stopCancel()
	service.StopService(stop)
	stopped = true
	// Closing the generated source requeues any unaccepted deliveries. A separate
	// native receiver proves the graph's result callback settled every input.
	check, err := client.NewConsumer(ctx, incoming, &rmq.ConsumerOptions{InitialCredits: 1, SettleStrategy: rmq.ExplicitSettle})
	if err != nil {
		t.Fatal(err)
	}
	defer check.Close(ctx)
	empty, emptyCancel := context.WithTimeout(ctx, 250*time.Millisecond)
	defer emptyCancel()
	if m, e := check.Receive(empty); e == nil {
		t.Fatalf("generated request completed without settlement: %+v", m.Message())
	} else if empty.Err() == nil {
		t.Fatalf("unexpected receiver failure: %v", e)
	}
}
