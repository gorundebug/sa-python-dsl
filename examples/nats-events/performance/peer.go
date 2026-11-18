// External load peer for the generated service. Never invokes SDK handlers.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	native "github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
	"io"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type event struct {
	ID    string `json:"id"`
	Value string `json:"value"`
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}
func emit(v any) { check(json.NewEncoder(os.Stdout).Encode(v)) }
func setting(name, fallback string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return fallback
}
func metrics() map[string]float64 {
	out := map[string]float64{}
	c := http.Client{Timeout: 2 * time.Second}
	r, e := c.Get("http://127.0.0.1:" + setting("METRICS_PORT", "8080") + "/metrics")
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
func main() {
	if len(os.Args) > 1 && os.Args[1] == "metrics" {
		emit(metrics())
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "cleanup" {
		nc, e := native.Connect(setting("NATS_URL", "nats://127.0.0.1:4222"))
		check(e)
		defer nc.Close()
		js, e := jetstream.New(nc)
		check(e)
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		for _, name := range []string{setting("INPUT_STREAM", "EXAMPLE_IN"), setting("OUTPUT_STREAM", "EXAMPLE_OUT")} {
			check(js.DeleteStream(ctx, name))
		}
		emit("cleaned")
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "resources" {
		resources()
		return
	}
	if len(os.Args) != 6 {
		panic("peer core|jetstream count inflight timeoutSeconds phase")
	}
	mode := os.Args[1]
	if mode != "core" && mode != "jetstream" {
		panic("invalid mode")
	}
	count, e := strconv.Atoi(os.Args[2])
	check(e)
	window, e := strconv.Atoi(os.Args[3])
	check(e)
	seconds, e := strconv.Atoi(os.Args[4])
	check(e)
	if count < 1 || count > 1000000 || window < 1 || window > 256 || seconds < 1 || seconds > 300 {
		panic("invalid bounded load")
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(seconds)*time.Second)
	defer cancel()
	var nc *native.Conn
	for {
		nc, e = native.Connect(setting("NATS_URL", "nats://127.0.0.1:4222"), native.Timeout(time.Second), native.NoReconnect())
		if e == nil {
			break
		}
		select {
		case <-ctx.Done():
			panic(ctx.Err())
		case <-time.After(50 * time.Millisecond):
		}
	}
	defer nc.Close()
	js, e := jetstream.New(nc, jetstream.WithPublishAsyncMaxPending(window))
	check(e)
	// Wait for generated service startup, not just broker readiness.
	for {
		_, e = js.Consumer(ctx, setting("INPUT_STREAM", "EXAMPLE_IN"), "event_processor")
		if e == nil {
			break
		}
		select {
		case <-ctx.Done():
			panic(ctx.Err())
		case <-time.After(50 * time.Millisecond):
		}
	}
	prefix := setting("SUBJECT_PREFIX", "example")
	in, out := prefix+".core.incoming", prefix+".core.processed"
	if mode == "jetstream" {
		in, out = prefix+".durable.incoming", prefix+".durable.processed"
	}
	var mu sync.Mutex
	pending := map[string]chan time.Time{}
	var unexpected atomic.Int64
	var invalid atomic.Int64
	sub, e := nc.Subscribe(out, func(m *native.Msg) {
		var v event
		if json.Unmarshal(m.Data, &v) != nil || v.Value != "HELLO PERFORMANCE" {
			invalid.Add(1)
			return
		}
		mu.Lock()
		ch := pending[v.ID]
		if ch != nil {
			delete(pending, v.ID)
		}
		mu.Unlock()
		if ch == nil {
			unexpected.Add(1)
			return
		}
		ch <- time.Now()
	})
	check(e)
	check(sub.SetPendingLimits(window*2, 4<<20))
	check(nc.FlushWithContext(ctx))
	var initialOutputs uint64
	if mode == "jetstream" {
		stream, err := js.Stream(ctx, setting("OUTPUT_STREAM", "EXAMPLE_OUT"))
		check(err)
		info, err := stream.Info(ctx)
		check(err)
		initialOutputs = info.State.Msgs
	}
	before := metrics()
	latencies := make([]float64, count)
	var next atomic.Int64
	var acked atomic.Int64
	errors := make(chan error, window)
	var wg sync.WaitGroup
	start := time.Now()
	for worker := 0; worker < window; worker++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				index := int(next.Add(1) - 1)
				if index >= count {
					return
				}
				id := fmt.Sprintf("%s-%s-%d", mode, os.Args[5], index)
				ch := make(chan time.Time, 1)
				mu.Lock()
				pending[id] = ch
				mu.Unlock()
				payload, _ := json.Marshal(event{id, " hello performance "})
				if os.Getenv("WIRE_UPPER") == "1" {
					payload, _ = json.Marshal(map[string]string{"ID": id, "Value": " hello performance "})
				}
				sent := time.Now()
				if mode == "core" {
					if err := nc.Publish(in, payload); err != nil {
						errors <- err
						cancel()
						return
					}
				} else {
					future, err := js.PublishAsync(in, payload)
					if err != nil {
						errors <- err
						cancel()
						return
					}
					select {
					case <-future.Ok():
						acked.Add(1)
					case err := <-future.Err():
						errors <- err
						cancel()
						return
					case <-ctx.Done():
						errors <- ctx.Err()
						return
					}
				}
				select {
				case received := <-ch:
					latencies[index] = float64(received.Sub(sent).Nanoseconds()) / 1e6
				case <-ctx.Done():
					errors <- ctx.Err()
					return
				}
			}
		}()
	}
	wg.Wait()
	elapsed := time.Since(start)
	close(errors)
	for err := range errors {
		check(err)
	}
	check(nc.LastError())
	if unexpected.Load() != 0 || invalid.Load() != 0 {
		panic("duplicate/unexpected/invalid normalized output")
	}
	var settlement any = nil
	if mode == "jetstream" {
		stream, err := js.Stream(ctx, setting("OUTPUT_STREAM", "EXAMPLE_OUT"))
		check(err)
		info, err := stream.Info(ctx)
		check(err)
		if info.State.Msgs != initialOutputs+uint64(count) {
			panic("stored output count mismatch")
		}
		for {
			consumer, err := js.Consumer(ctx, setting("INPUT_STREAM", "EXAMPLE_IN"), "event_processor")
			check(err)
			ci, err := consumer.Info(ctx)
			check(err)
			if ci.NumAckPending == 0 && ci.NumPending == 0 && ci.AckFloor.Consumer >= info.State.Msgs {
				settlement = map[string]any{"source_ack_floor": ci.AckFloor.Consumer, "source_ack_pending": ci.NumAckPending, "source_pending": ci.NumPending, "stored_outputs": info.State.Msgs, "input_pubacks": acked.Load()}
				break
			}
			select {
			case <-ctx.Done():
				panic(ctx.Err())
			case <-time.After(5 * time.Millisecond):
			}
		}
	}
	settledElapsed := time.Since(start)
	after := metrics()
	sort.Float64s(latencies)
	percentile := func(p float64) float64 { return latencies[int(float64(count-1)*p)] }
	deltas := map[string]any{}
	for _, n := range []string{"process_cpu_seconds_total", "go_memstats_mallocs_total", "go_memstats_alloc_bytes_total"} {
		a, ok := after[n]
		b, bok := before[n]
		if ok && bok {
			deltas[n] = a - b
		} else {
			deltas[n] = nil
		}
	}
	emit(map[string]any{"mode": mode, "phase": os.Args[5], "count": count, "inflight_limit": window, "round_trip_seconds": elapsed.Seconds(), "messages_per_second": float64(count) / elapsed.Seconds(), "latency_ms": map[string]float64{"p50": percentile(.50), "p95": percentile(.95), "p99": percentile(.99)}, "settled_seconds": settledElapsed.Seconds(), "settled_messages_per_second": float64(count) / settledElapsed.Seconds(), "jetstream_settlement": settlement, "metric_deltas": deltas, "metrics_before": before, "metrics_after": after, "invalid": invalid.Load(), "unexpected": unexpected.Load()})
}
