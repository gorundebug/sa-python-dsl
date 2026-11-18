package app

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"reflect"
	"testing"
	"time"

	"example.com/pulsar-events/eventprocessor/internal/config"
	"example.com/pulsar-events/eventprocessor/internal/types"
	native "github.com/apache/pulsar-client-go/pulsar"
	"github.com/gorundebug/servicelib/runtime"
)

func TestCanonicalPulsarEventPipelines(t *testing.T) {
	admin := os.Getenv("PULSAR_TEST_ADMIN_URL")
	if admin == "" {
		t.Fatal("PULSAR_TEST_ADMIN_URL required")
	}
	address := os.Getenv("PULSAR_TEST_URL")
	if address == "" {
		address = "pulsar://127.0.0.1:16650"
	}
	ctx, cancel := context.WithTimeout(t.Context(), 30*time.Second)
	defer cancel()
	ns := "public/sa-canonical-" + runtime.NewStreamID()
	request := func(method, path string, body any) []byte {
		t.Helper()
		data, err := json.Marshal(body)
		if err != nil {
			t.Fatal(err)
		}
		requestCtx, done := context.WithTimeout(context.WithoutCancel(ctx), 5*time.Second)
		defer done()
		req, err := http.NewRequestWithContext(requestCtx, method, admin+path, bytes.NewReader(data))
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set("Content-Type", "application/json")
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()
		result, err := io.ReadAll(resp.Body)
		if err != nil {
			t.Fatal(err)
		}
		if resp.StatusCode == 404 && method == "DELETE" {
			return nil
		}
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			t.Fatalf("%s %s: %d %s", method, path, resp.StatusCode, result)
		}
		return result
	}
	request("PUT", "/admin/v2/namespaces/"+ns, map[string]any{})
	// Only the disposable fixture provisions its namespace; application startup
	// creates the explicitly requested topics/subscription, not namespace policies.
	request("POST", "/admin/v2/namespaces/"+ns+"/autoTopicCreation", map[string]any{"allowAutoTopicCreation": false})
	request("POST", "/admin/v2/namespaces/"+ns+"/autoSubscriptionCreation", map[string]any{"allowAutoSubscriptionCreation": false})
	t.Cleanup(func() {
		for _, topic := range []string{"incoming", "processed"} {
			request("DELETE", "/admin/v2/persistent/"+ns+"/"+topic+"?force=true", nil)
		}
		request("DELETE", "/admin/v2/namespaces/"+ns, nil)
	})
	incoming, processed := "persistent://"+ns+"/incoming", "persistent://"+ns+"/processed"
	for _, name := range []string{"SERVICELIB_NOOP_METRICS", "SERVICELIB_NOOP_LOGS", "SERVICELIB_NOOP_TRACING"} {
		t.Setenv(name, "1")
	}
	for name, value := range map[string]string{"EVENTS_SERVERS": address, "EVENTS_ADMIN_URL": admin, "EVENTS_ADMIN_TOKEN": "test-runtime-admin", "RECEIVE_EVENT_TOPIC": incoming, "PUBLISH_EVENT_TOPIC": processed, "EVENT_PROCESSOR_HTTP_PORT": "0", "EVENT_PROCESSOR_GRPC_PORT": "0"} {
		t.Setenv(name, value)
	}
	configured := config.MakeConfig()
	if err := configured.ApplyEnvironment(); err != nil {
		t.Fatal(err)
	}
	if configured.DataConnectors.Events.AdminToken != "test-runtime-admin" || configured.DataConnectors.Events.AdminURL != admin || configured.Endpoints.ReceiveEvent.Topic != incoming || configured.Endpoints.PublishEvent.Topic != processed {
		t.Fatal("environment override lost")
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
		stop, done := context.WithTimeout(context.WithoutCancel(ctx), 3*time.Second)
		defer done()
		service.StopService(stop)
	}()
	for _, record := range []any{types.Event{ID: "serde", Value: "value"}, types.PublicationOutcome{EventID: "serde", MessageID: "native-id", Accepted: true}} {
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
	client, err := native.NewClient(native.ClientOptions{URL: address, OperationTimeout: 3 * time.Second})
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()
	producer, err := client.CreateProducer(native.ProducerOptions{Topic: incoming, DisableBatching: true})
	if err != nil {
		t.Fatal(err)
	}
	defer producer.Close()
	reader, err := client.CreateReader(native.ReaderOptions{Topic: processed, StartMessageID: native.EarliestMessageID()})
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	for i := 0; i < 3; i++ {
		payload, e := json.Marshal(types.Event{ID: fmt.Sprintf("event-%d", i), Value: " hello "})
		if e != nil {
			t.Fatal(e)
		}
		if _, e = producer.Send(ctx, &native.ProducerMessage{Payload: payload}); e != nil {
			t.Fatal(e)
		}
	}
	seen := map[string]bool{}
	for i := 0; i < 3; i++ {
		message, e := reader.Next(ctx)
		if e != nil {
			t.Fatal(e)
		}
		var value types.Event
		if e = json.Unmarshal(message.Payload(), &value); e != nil {
			t.Fatal(e)
		}
		if value.Value != "HELLO" || message.Key() != value.ID || seen[value.ID] {
			t.Fatalf("unexpected output: %+v", value)
		}
		seen[value.ID] = true
	}
	for i := 0; i < 3; i++ {
		if !seen[fmt.Sprintf("event-%d", i)] {
			t.Fatal("missing event")
		}
	}
	// Individual source ACK is asynchronous. Observe broker state rather than
	// treating callback return or local Done as settlement proof.
	ticker := time.NewTicker(20 * time.Millisecond)
	defer ticker.Stop()
	for {
		var stats struct {
			Subscriptions map[string]struct {
				MsgBacklog      int64 `json:"msgBacklog"`
				UnackedMessages int64 `json:"unackedMessages"`
			} `json:"subscriptions"`
		}
		if err = json.Unmarshal(request("GET", "/admin/v2/persistent/"+ns+"/incoming/stats", nil), &stats); err != nil {
			t.Fatal(err)
		}
		sub, ok := stats.Subscriptions["event_processors"]
		if ok && sub.MsgBacklog == 0 && sub.UnackedMessages == 0 {
			break
		}
		select {
		case <-ctx.Done():
			t.Fatal("source ACK not observed")
		case <-ticker.C:
		}
	}
}
