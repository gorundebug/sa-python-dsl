package app

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strconv"
	"testing"
	"time"

	"example.com/nats-events/eventprocessor/internal/config"
	"example.com/nats-events/eventprocessor/internal/types"
	"github.com/gorundebug/servicelib/runtime"
	native "github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
)

// This test starts the generated graph and both native transports. It does not
// call endpoint handlers directly or replace the broker with a mock.
func TestCanonicalNATSEventPipelines(t *testing.T) {
	binary := os.Getenv("NATS_SERVER_BINARY")
	if binary == "" {
		t.Skip("set NATS_SERVER_BINARY for native broker acceptance")
	}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	port := listener.Addr().(*net.TCPAddr).Port
	listener.Close()
	log, err := os.Create(filepath.Join(t.TempDir(), "broker.log"))
	if err != nil {
		t.Fatal(err)
	}
	defer log.Close()
	process := exec.Command(binary, "-js", "-a", "127.0.0.1", "-p", strconv.Itoa(port), "-sd", t.TempDir())
	process.Stdout, process.Stderr = log, log
	if err = process.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { process.Process.Kill(); process.Wait() }()
	address := "nats://127.0.0.1:" + strconv.Itoa(port)
	ctx, cancel := context.WithTimeout(t.Context(), 30*time.Second)
	defer cancel()
	var client *native.Conn
	for deadline := time.Now().Add(5 * time.Second); time.Now().Before(deadline); {
		client, err = native.Connect(address, native.Timeout(100*time.Millisecond))
		if err == nil {
			break
		}
		time.Sleep(20 * time.Millisecond)
	}
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()
	observed, err := client.SubscribeSync("example.core.processed")
	if err != nil {
		t.Fatal(err)
	}
	if err = client.FlushWithContext(ctx); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"SERVICELIB_NOOP_METRICS", "SERVICELIB_NOOP_LOGS", "SERVICELIB_NOOP_TRACING"} {
		t.Setenv(name, "1")
	}
	t.Setenv("CORE_EVENTS_SERVERS", address)
	t.Setenv("DURABLE_EVENTS_SERVERS", address)
	t.Setenv("EVENT_PROCESSOR_HTTP_PORT", "0")
	t.Setenv("EVENT_PROCESSOR_GRPC_PORT", "0")
	service, err := runtime.MakeService[*Service, *config.Config](ctx, "EventProcessor", &serviceDependencies{}, nil, nil,
		func() *Service { return &Service{} }, func() *config.Config {
			c := config.MakeConfig()
			c.Services.EventProcessor.HttpPort = 0
			c.Services.EventProcessor.GrpcPort = 0
			c.DataConnectors.CoreEvents.Servers = []string{address}
			c.DataConnectors.DurableEvents.Servers = []string{address}
			return c
		})
	if err != nil {
		t.Fatal(err)
	}
	defer service.Release(ctx)
	if err = service.StartService(ctx); err != nil {
		t.Fatal(err)
	}
	defer service.StopService(ctx)
	// Native transferByValue records must resolve to value serializers at runtime.
	for _, record := range []any{types.Event{ID: "serde", Value: "record"}, types.PublicationOutcome{EventID: "serde", Accepted: true}} {
		codec, e := service.GetSerde(reflect.TypeOf(record))
		if e != nil || codec == nil {
			t.Fatalf("serializer resolution: %v", e)
		}
		encoded, e := codec.SerializeObj(record, nil)
		if e != nil {
			t.Fatal(e)
		}
		decoded, e := codec.DeserializeObj(encoded)
		if e != nil || !reflect.DeepEqual(record, decoded) {
			t.Fatalf("record round trip: %+v, %v", decoded, e)
		}
	}

	js, err := jetstream.New(client)
	if err != nil {
		t.Fatal(err)
	}
	const count = 3
	for i := 0; i < count; i++ {
		id := fmt.Sprintf("core-%d", i)
		payload, _ := json.Marshal(types.Event{ID: id, Value: " hello "})
		if err = client.Publish("example.core.incoming", payload); err != nil {
			t.Fatal(err)
		}
		message, e := observed.NextMsgWithContext(ctx)
		if e != nil {
			t.Fatal(e)
		}
		var event types.Event
		if e = json.Unmarshal(message.Data, &event); e != nil {
			t.Fatal(e)
		}
		if event.ID != id || event.Value != "HELLO" {
			t.Fatalf("unexpected Core result: %+v", event)
		}
	}
	for i := 0; i < count; i++ {
		payload, _ := json.Marshal(types.Event{ID: fmt.Sprintf("durable-%d", i), Value: " world "})
		if _, err = js.Publish(ctx, "example.durable.incoming", payload); err != nil {
			t.Fatal(err)
		}
	}
	consumer, err := js.Consumer(ctx, "EXAMPLE_IN", "event_processor")
	if err != nil {
		t.Fatal(err)
	}
	for {
		info, e := consumer.Info(ctx)
		if e != nil {
			t.Fatal(e)
		}
		if info.AckFloor.Consumer >= count && info.NumAckPending == 0 && info.NumPending == 0 {
			break
		}
		select {
		case <-ctx.Done():
			t.Fatal("generated pipeline never acknowledged confirmed publications", ctx.Err())
		case <-time.After(20 * time.Millisecond):
		}
	}
	stream, err := js.Stream(ctx, "EXAMPLE_OUT")
	if err != nil {
		t.Fatal(err)
	}
	info, err := stream.Info(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if info.State.Msgs != count {
		t.Fatalf("expected %d output messages, got %d", count, info.State.Msgs)
	}
	for seq := uint64(1); seq <= count; seq++ {
		message, e := stream.GetMsg(ctx, seq)
		if e != nil {
			t.Fatal(e)
		}
		var event types.Event
		if e = json.Unmarshal(message.Data, &event); e != nil {
			t.Fatal(e)
		}
		if event.ID != fmt.Sprintf("durable-%d", seq-1) || event.Value != "WORLD" {
			t.Fatalf("unexpected JetStream result: %+v", event)
		}
	}
}
