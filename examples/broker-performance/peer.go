// External official-client load peer; never calls generated handlers or SDK adapters.
package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	amqp "github.com/Azure/go-amqp"
	pulsar "github.com/apache/pulsar-client-go/pulsar"
	rabbit "github.com/rabbitmq/rabbitmq-amqp-go-client/pkg/rabbitmqamqp"
	redis "github.com/redis/go-redis/v9"
	"io"
	"net/http"

	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

type event struct {
	ID    string `json:"ID"`
	Value string `json:"Value"`
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}
func emit(v any) { check(json.NewEncoder(os.Stdout).Encode(v)) }
func metrics() map[string]float64 {
	out := map[string]float64{}
	c := http.Client{Timeout: 2 * time.Second}
	r, e := c.Get("http://127.0.0.1:" + os.Getenv("METRICS_PORT") + "/metrics")
	if e != nil {
		return out
	}
	defer r.Body.Close()
	b, _ := io.ReadAll(io.LimitReader(r.Body, 4<<20))
	for _, line := range strings.Split(string(b), "\n") {
		f := strings.Fields(line)
		if len(f) == 2 && !strings.Contains(f[0], "{") {
			v, e := strconv.ParseFloat(f[1], 64)
			if e == nil {
				out[f[0]] = v
			}
		}
	}
	return out
}

// Availability does not require Go-style unlabelled process counters.
func metricsAvailable() bool {
	c := http.Client{Timeout: 2 * time.Second}
	r, err := c.Get("http://127.0.0.1:" + os.Getenv("METRICS_PORT") + "/metrics")
	if err != nil {
		return false
	}
	defer r.Body.Close()
	if r.StatusCode != http.StatusOK {
		return false
	}
	body, err := io.ReadAll(io.LimitReader(r.Body, 4<<20))
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(body), "\n") {
		fields := strings.Fields(line)
		if len(fields) >= 2 && !strings.HasPrefix(fields[0], "#") {
			if _, err := strconv.ParseFloat(fields[len(fields)-1], 64); err == nil {
				return true
			}
		}
	}
	return false
}
func resources() {
	out := map[string]string{}
	for _, n := range []string{"cpu.max", "cpu.stat", "memory.current", "memory.peak", "memory.max"} {
		b, e := os.ReadFile("/sys/fs/cgroup/" + n)
		if e == nil {
			out[n] = string(b)
		}
	}
	emit(out)
}
func admin(method, path string, body any) map[string]any {
	var data io.Reader
	if body != nil {
		b, e := json.Marshal(body)
		check(e)
		data = bytes.NewReader(b)
	}
	req, e := http.NewRequest(method, os.Getenv("ADMIN_URL")+path, data)
	check(e)
	req.Header.Set("Content-Type", "application/json")
	if os.Getenv("MODE") == "rabbitmq" {
		req.SetBasicAuth("adapter", os.Getenv("BROKER_PASSWORD"))
	}
	res, e := (&http.Client{Timeout: 3 * time.Second}).Do(req)
	check(e)
	defer res.Body.Close()
	if res.StatusCode == 404 && method == "DELETE" {
		return nil
	}
	if res.StatusCode >= 300 {
		panic(fmt.Sprintf("admin %s %s status %d", method, path, res.StatusCode))
	}
	var out map[string]any
	json.NewDecoder(res.Body).Decode(&out)
	return out
}
func main() {
	if len(os.Args) > 1 && os.Args[1] == "ready" {
		emit(metricsAvailable())
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "metrics" {
		emit(metrics())
		return
	}

	if len(os.Args) > 1 && os.Args[1] == "resources" {
		resources()
		return
	}
	mode := os.Getenv("MODE")
	id := os.Getenv("RUN_ID")
	input := id + ".incoming"
	output := id + ".processed"
	action := os.Args[1]
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	var pub func(context.Context, event) error
	var recv func(context.Context) (event, string, error)
	var settlement func() (bool, any)
	var cleanup func()
	total, _ := strconv.Atoi(os.Getenv("EXPECTED_TOTAL"))
	switch mode {
	case "redis-streams":
		c := redis.NewClient(&redis.Options{Addr: "127.0.0.1:6379", Password: os.Getenv("BROKER_PASSWORD"), MaxRetries: -1, PoolSize: 32})
		defer c.Close()
		if action == "prepare" {
			check(c.XGroupCreateMkStream(ctx, input, "event_processors", "0-0").Err())
			check(c.XGroupCreateMkStream(ctx, output, "perf", "0-0").Err())
			emit("prepared")
			return
		}
		cleanup = func() { check(c.Del(ctx, input, output).Err()) }
		pub = func(ctx context.Context, v event) error {
			return c.XAdd(ctx, &redis.XAddArgs{Stream: input, Values: []any{"ID", v.ID, "Value", v.Value}}).Err()
		}
		recv = func(ctx context.Context) (event, string, error) {
			rows, e := c.XReadGroup(ctx, &redis.XReadGroupArgs{Group: "perf", Consumer: "peer", Streams: []string{output, ">"}, Count: 1, Block: time.Second}).Result()
			if e != nil {
				return event{}, "", e
			}
			m := rows[0].Messages[0]
			v := event{ID: fmt.Sprint(m.Values["ID"]), Value: fmt.Sprint(m.Values["Value"])}
			e = c.XAck(ctx, output, "perf", m.ID).Err()
			return v, m.ID, e
		}
		settlement = func() (bool, any) {
			p, e := c.XPending(ctx, input, "event_processors").Result()
			check(e)
			g, e := c.XInfoGroups(ctx, input).Result()
			check(e)
			n, e := c.XLen(ctx, output).Result()
			check(e)
			lag := int64(-1)
			for _, x := range g {
				if x.Name == "event_processors" {
					lag = x.Lag
				}
			}
			return p.Count == 0 && lag == 0 && n == int64(total), map[string]any{"input_pending": p.Count, "input_lag": lag, "output_length": n, "meaning": "XADD ID; explicit input XACK; no replica/disk guarantee"}
		}
	case "rabbitmq":
		c, e := rabbit.Dial(ctx, "amqp://127.0.0.1:5672", &rabbit.AmqpConnOptions{SASLType: amqp.SASLTypePlain("adapter", os.Getenv("BROKER_PASSWORD")), RecoveryConfiguration: &rabbit.RecoveryConfiguration{ActiveRecovery: false}, TopologyRecoveryOptions: rabbit.TopologyRecoveryDisabled})
		check(e)
		defer c.Close(context.Background())
		if action == "prepare" {
			_, e = c.Management().DeclareQueue(ctx, &rabbit.QuorumQueueSpecification{Name: input})
			check(e)
			_, e = c.Management().DeclareQueue(ctx, &rabbit.QuorumQueueSpecification{Name: output})
			check(e)
			emit("prepared")
			return
		}
		cleanup = func() {
			e := c.Management().DeleteQueue(ctx, input)
			check(e)
			e = c.Management().DeleteQueue(ctx, output)
			check(e)
			check(c.Management().DeleteExchange(ctx, id+".events"))
		}
		if action != "cleanup" {
			p, e := c.NewPublisher(ctx, &rabbit.QueueAddress{Queue: input}, &rabbit.PublisherOptions{MaxInFlight: 32})
			check(e)
			defer p.Close(context.Background())
			sub, e := c.NewConsumer(ctx, output, &rabbit.ConsumerOptions{InitialCredits: 32, SettleStrategy: rabbit.ExplicitSettle})
			check(e)
			defer sub.Close(context.Background())
			pub = func(ctx context.Context, v event) error {
				b, e := json.Marshal(v)
				if e != nil {
					return e
				}
				r, e := p.Publish(ctx, rabbit.NewMessage(b))
				if e != nil {
					return e
				}
				if _, ok := r.Outcome.(*rabbit.StateAccepted); !ok {
					return fmt.Errorf("input outcome %T", r.Outcome)
				}
				return nil
			}
			recv = func(ctx context.Context) (event, string, error) {
				d, e := sub.Receive(ctx)
				if e != nil {
					return event{}, "", e
				}
				var v event
				b := d.Message().GetData()
				if len(b) == 0 {
					switch x := d.Message().Value.(type) {
					case []byte:
						b = x
					case string:
						b = []byte(x)
					}
				}
				e = json.Unmarshal(b, &v)
				if e == nil {
					e = d.Accept(ctx)
				}
				return v, v.ID, e
			}
		}
		settlement = func() (bool, any) {
			r, e := (&http.Client{Timeout: 3 * time.Second}).Get(os.Getenv("ADMIN_URL") + "/metrics/per-object")
			check(e)
			defer r.Body.Close()
			body, e := io.ReadAll(io.LimitReader(r.Body, 16<<20))
			check(e)
			values := map[string]float64{}
			for _, line := range strings.Split(string(body), "\n") {
				for _, q := range []string{input, output} {
					if !strings.Contains(line, `queue="`+q+`"`) {
						continue
					}
					f := strings.Fields(line)
					if len(f) != 2 {
						continue
					}
					for _, metric := range []string{"rabbitmq_queue_messages_ready", "rabbitmq_queue_messages_unacked", "rabbitmq_queue_messages_acked_total"} {
						if strings.HasPrefix(f[0], metric+"{") {
							v, e := strconv.ParseFloat(f[1], 64)
							check(e)
							values[q+":"+metric] = v
						}
					}
				}
			}
			ok := true
			for _, q := range []string{input, output} {
				for _, m := range []string{"rabbitmq_queue_messages_ready", "rabbitmq_queue_messages_unacked"} {
					v, found := values[q+":"+m]
					ok = ok && found && v == 0
				}
			}
			return ok, map[string]any{"queue_metrics": values, "meaning": "native StateAccepted inputs; canonical explicit input acceptance; source/output queue ready and unacked zero. ACK counter availability differs by protocol"}
		}

	case "pulsar":
		ns := "public/" + id
		in := "persistent://" + ns + "/incoming"
		out := "persistent://" + ns + "/processed"
		base := "/admin/v2/persistent/" + ns
		if action == "prepare" {
			admin("PUT", "/admin/v2/namespaces/"+ns, map[string]any{})
			admin("POST", "/admin/v2/namespaces/"+ns+"/autoTopicCreation", map[string]any{"allowAutoTopicCreation": false})
			admin("POST", "/admin/v2/namespaces/"+ns+"/autoSubscriptionCreation", map[string]any{"allowAutoSubscriptionCreation": false})
			for _, topic := range []string{"incoming", "processed"} {
				admin("PUT", base+"/"+topic, nil)
			}
			admin("PUT", base+"/processed/subscription/perf", map[string]any{"ledgerId": -1, "entryId": -1})
			emit("prepared")
			return
		}
		cleanup = func() {
			for _, topic := range []string{"incoming", "processed"} {
				admin("DELETE", base+"/"+topic+"?force=true", nil)
			}
			admin("DELETE", "/admin/v2/namespaces/"+ns, nil)
		}
		if action != "cleanup" {
			c, e := pulsar.NewClient(pulsar.ClientOptions{URL: "pulsar://127.0.0.1:16650", OperationTimeout: 5 * time.Second})
			check(e)
			defer c.Close()
			p, e := c.CreateProducer(pulsar.ProducerOptions{Topic: in, DisableBatching: true, MaxPendingMessages: 32})
			check(e)
			defer p.Close()
			sub, e := c.Subscribe(pulsar.ConsumerOptions{Topic: out, SubscriptionName: "perf", Type: pulsar.Exclusive, ReceiverQueueSize: 32})
			check(e)
			defer sub.Close()
			pub = func(ctx context.Context, v event) error {
				b, e := json.Marshal(v)
				if e != nil {
					return e
				}
				_, e = p.Send(ctx, &pulsar.ProducerMessage{Payload: b, Key: v.ID})
				return e
			}
			recv = func(ctx context.Context) (event, string, error) {
				m, e := sub.Receive(ctx)
				if e != nil {
					return event{}, "", e
				}
				var v event
				e = json.Unmarshal(m.Payload(), &v)
				if e == nil && m.Key() != v.ID {
					e = fmt.Errorf("key mismatch")
				}
				if e == nil {
					e = sub.Ack(m)
				}
				return v, base64.StdEncoding.EncodeToString(m.ID().Serialize()), e
			}
		}
		settlement = func() (bool, any) {
			s := admin("GET", base+"/incoming/stats", nil)
			subs, _ := s["subscriptions"].(map[string]any)
			sub, _ := subs["event_processors"].(map[string]any)
			backlog, bok := sub["msgBacklog"].(float64)
			unacked, uok := sub["unackedMessages"].(float64)
			outStats := admin("GET", base+"/processed/stats", nil)
			outSubs, _ := outStats["subscriptions"].(map[string]any)
			outSub, _ := outSubs["perf"].(map[string]any)
			outBacklog, obok := outSub["msgBacklog"].(float64)
			outUnacked, ouok := outSub["unackedMessages"].(float64)
			return bok && uok && obok && ouok && backlog == 0 && unacked == 0 && outBacklog == 0 && outUnacked == 0, map[string]any{"output_backlog": outBacklog, "output_unacked": outUnacked, "input_backlog": backlog, "input_unacked": unacked, "meaning": "native output MessageID; explicit individual input ACK observed via backlog/unacked, not downstream proof"}
		}
	default:
		panic("unsupported broker")
	}
	if action == "cleanup" {
		cleanup()
		emit("cleaned")
		return
	}
	count, e := strconv.Atoi(os.Args[2])
	check(e)
	window, e := strconv.Atoi(os.Args[3])
	check(e)
	seconds, e := strconv.Atoi(os.Args[4])
	check(e)
	if count < 1 || count > 1000000 || window < 1 || window > 32 || seconds < 1 || seconds > 300 {
		panic("invalid bounds")
	}
	cancel()
	ctx, cancel = context.WithTimeout(context.Background(), time.Duration(seconds)*time.Second)
	defer cancel()
	before := metrics()
	if !metricsAvailable() {
		panic("service metrics unavailable")
	}
	var mu sync.Mutex
	pending := map[string]chan time.Time{}
	seen := map[string]bool{}
	nativeIDs := map[string]bool{}
	receiveDone := make(chan struct{})
	go func() {
		defer close(receiveDone)
		for i := 0; i < count; {
			v, mid, e := recv(ctx)
			if e == redis.Nil {
				continue
			}
			check(e)
			now := time.Now()
			mu.Lock()
			ch := pending[v.ID]
			if ch == nil || seen[v.ID] || v.Value != "HELLO PERFORMANCE" || mid == "" || nativeIDs[mid] {
				panic(fmt.Sprintf("invalid output id=%q value=%q pending=%t seen=%t identity=%q identity_seen=%t", v.ID, v.Value, ch != nil, seen[v.ID], mid, nativeIDs[mid]))
			}
			seen[v.ID] = true
			nativeIDs[mid] = true
			mu.Unlock()
			ch <- now
			i++
		}
	}()
	lat := make([]float64, count)
	jobs := make(chan int)
	var wg sync.WaitGroup
	start := time.Now()
	for w := 0; w < window; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := range jobs {
				key := id + "-" + action + "-" + strconv.Itoa(i)
				ch := make(chan time.Time, 1)
				mu.Lock()
				pending[key] = ch
				mu.Unlock()
				sent := time.Now()
				check(pub(ctx, event{key, " hello performance "}))
				select {
				case received := <-ch:
					lat[i] = float64(received.Sub(sent).Nanoseconds()) / 1e6
				case <-ctx.Done():
					panic(ctx.Err())
				}
				mu.Lock()
				delete(pending, key)
				mu.Unlock()
			}
		}()
	}
	for i := 0; i < count; i++ {
		select {
		case jobs <- i:
		case <-ctx.Done():
			panic(ctx.Err())
		}
	}
	close(jobs)
	wg.Wait()
	<-receiveDone
	elapsed := time.Since(start)
	var evidence any
	for {
		ok, v := settlement()
		evidence = v
		if ok {
			break
		}
		select {
		case <-ctx.Done():
			panic(ctx.Err())
		case <-time.After(50 * time.Millisecond):
		}
	}
	settled := time.Since(start)
	after := metrics()
	sort.Float64s(lat)
	deltas := map[string]any{}
	for _, name := range []string{"process_cpu_seconds_total", "go_memstats_mallocs_total", "go_memstats_alloc_bytes_total"} {
		a, aok := after[name]
		b, bok := before[name]
		if aok && bok {
			deltas[name] = a - b
		} else {
			deltas[name] = nil
		}
	}
	emit(map[string]any{"mode": mode, "phase": action, "count": count, "inflight_limit": window, "round_trip_seconds": elapsed.Seconds(), "messages_per_second": float64(count) / elapsed.Seconds(), "settled_seconds": settled.Seconds(), "settled_messages_per_second": float64(count) / settled.Seconds(), "latency_ms": map[string]float64{"p50": lat[(count-1)/2], "p95": lat[(count-1)*95/100], "p99": lat[(count-1)*99/100]}, "validated_outputs": len(seen), "input_native_success": count, "unique_output_identities": len(nativeIDs), "settlement": evidence, "metric_deltas": deltas, "metrics_before": before, "metrics_after": after})
}
