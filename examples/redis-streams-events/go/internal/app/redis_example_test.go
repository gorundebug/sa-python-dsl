package app

import (
	"context"
	"example.com/redis-streams-events/eventprocessor/internal/config"
	"example.com/redis-streams-events/eventprocessor/internal/types"
	"fmt"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/redis/go-redis/v9"
	"os"
	"reflect"
	"testing"
	"time"
)

func TestCanonicalRedisStreamsEventPipelines(t *testing.T) {
	address := os.Getenv("REDIS_STREAMS_TEST_URL")
	if address == "" {
		t.Skip("set REDIS_STREAMS_TEST_URL")
	}
	ctx, cancel := context.WithTimeout(t.Context(), 20*time.Second)
	defer cancel()
	options, err := redis.ParseURL(address)
	if err != nil {
		t.Fatal(err)
	}
	options.Password = os.Getenv("REDIS_STREAMS_TEST_PASSWORD")
	client := redis.NewClient(options)
	defer client.Close()
	suffix := runtime.NewStreamID()
	incoming, processed := "example.in."+suffix, "example.out."+suffix
	defer client.Del(ctx, incoming, processed)
	for _, name := range []string{"SERVICELIB_NOOP_METRICS", "SERVICELIB_NOOP_LOGS", "SERVICELIB_NOOP_TRACING"} {
		t.Setenv(name, "1")
	}
	for name, value := range map[string]string{"EVENTS_SERVERS": address, "EVENTS_PASSWORD": options.Password, "RECEIVE_EVENT_STREAM_KEY": incoming, "PUBLISH_EVENT_STREAM_KEY": processed, "EVENT_PROCESSOR_HTTP_PORT": "0", "EVENT_PROCESSOR_GRPC_PORT": "0"} {
		t.Setenv(name, value)
	}
	configured := config.MakeConfig()
	if err := configured.ApplyEnvironment(); err != nil {
		t.Fatal(err)
	}
	if configured.DataConnectors.Events.Password != options.Password || configured.Endpoints.ReceiveEvent.StreamKey != incoming || configured.Endpoints.PublishEvent.StreamKey != processed {
		t.Fatal("generated environment configuration lost")
	}
	service, err := runtime.MakeService[*Service, *config.Config](ctx, "EventProcessor", &serviceDependencies{}, nil, nil, func() *Service { return &Service{} }, config.MakeConfig)
	if err != nil {
		t.Fatal(err)
	}
	defer service.Release(ctx)
	if err = service.StartService(ctx); err != nil {
		t.Fatal(err)
	}
	defer func() {
		stop, cancel := context.WithTimeout(ctx, 3*time.Second)
		defer cancel()
		service.StopService(stop)
	}()
	for _, record := range []any{types.Event{ID: "serde", Value: "record"}, types.PublicationOutcome{EventID: "serde", EntryID: "1-0", Accepted: true}} {
		codec, e := service.GetSerde(reflect.TypeOf(record))
		if e != nil || codec == nil {
			t.Fatalf("serde: %v", e)
		}
		encoded, e := codec.SerializeObj(record, nil)
		if e != nil {
			t.Fatal(e)
		}
		decoded, e := codec.DeserializeObj(encoded)
		if e != nil || !reflect.DeepEqual(record, decoded) {
			t.Fatalf("roundtrip: %v %v", decoded, e)
		}
	}
	for i := 0; i < 3; i++ {
		id := fmt.Sprintf("event-%d", i)
		if err = client.XAdd(ctx, &redis.XAddArgs{Stream: incoming, Values: map[string]interface{}{"ID": id, "Value": " hello "}}).Err(); err != nil {
			t.Fatal(err)
		}
	}
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()
	for {
		records, e := client.XRange(ctx, processed, "-", "+").Result()
		if e != nil {
			t.Fatal(e)
		}
		pending, e := client.XPending(ctx, incoming, "event_processors").Result()
		if e != nil {
			t.Fatal(e)
		}
		if len(records) == 3 && pending.Count == 0 {
			for i, r := range records {
				if r.Values["ID"] != fmt.Sprintf("event-%d", i) || r.Values["Value"] != "HELLO" {
					t.Fatalf("unexpected output: %+v", r)
				}
			}
			break
		}
		select {
		case <-ctx.Done():
			t.Fatalf("pipeline did not settle: output=%d pending=%d", len(records), pending.Count)
		case <-ticker.C:
		}
	}
}
