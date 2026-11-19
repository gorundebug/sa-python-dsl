package app

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"sync"
	"testing"
	"time"

	"example.com/storage-query/storageworker/internal/config"
	"example.com/storage-query/storageworker/internal/functions"
	"example.com/storage-query/storageworker/internal/types"
	"github.com/aws/aws-sdk-go-v2/aws"
	awscfg "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	s3types "github.com/aws/aws-sdk-go-v2/service/s3/types"
	"github.com/aws/smithy-go"
	"github.com/gorundebug/servicelib/dataquery/postgresqlbun"
	"github.com/gorundebug/servicelib/dataquery/s3aws"
	"github.com/gorundebug/servicelib/runtime"
)

// Test-only finalization observers preserve the real business methods and SDK I/O.
type observedRows struct {
	functions.RowsQuery
	ended chan error
}

func (h *observedRows) EndRequest(ctx context.Context, stream runtime.Stream, state functions.RowsQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], failures runtime.Collect[error]) {
	h.RowsQuery.EndRequest(ctx, stream, state, err, out, failures)
	h.ended <- err
}

type observedGet struct {
	functions.GetObjectQuery
	ended chan error
}

func (h *observedGet) EndRequest(ctx context.Context, stream runtime.Stream, state functions.GetObjectQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], failures runtime.Collect[error]) {
	h.GetObjectQuery.EndRequest(ctx, stream, state, err, out, failures)
	h.ended <- err
}

func TestLiveGeneratedQueryGraph(t *testing.T) {
	if os.Getenv("SA_QUERY_DISPOSABLE") != "1" {
		t.Skip("requires disposable local stores")
	}
	for _, flag := range []string{"SERVICELIB_NOOP_METRICS", "SERVICELIB_NOOP_TRACING", "SERVICELIB_NOOP_LOGS"} {
		t.Setenv(flag, "true")
	}
	port := func(name string) int {
		value, err := strconv.Atoi(os.Getenv(name))
		if err != nil || value < 1 || value > 65535 {
			t.Fatalf("invalid %s", name)
		}
		return value
	}
	pgPort, s3Port := port("SA_QUERY_PG_PORT"), port("SA_QUERY_S3_PORT")
	cfg := config.MakeConfig()
	cfg.DataConnectors.Database.ConnectionString = fmt.Sprintf("postgres://postgres@127.0.0.1:%d/query_example?sslmode=disable", pgPort)
	cfg.DataConnectors.Objects.Address = fmt.Sprintf("http://127.0.0.1:%d", s3Port)
	cfg.DataConnectors.Objects.ForcePathStyle = true
	path := filepath.Join(t.TempDir(), "config.yaml")
	if err := os.WriteFile(path, []byte("{}\n"), 0600); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(t.Context(), 15*time.Second)
	defer cancel()
	service, err := runtime.MakeService[*Service, *config.Config](ctx, "StorageWorker", &serviceDependencies{}, &path, &path, func() *Service { return &Service{} }, func() *config.Config { return cfg })
	if err != nil {
		t.Fatal(err)
	}
	defer service.Release(ctx)
	if err := service.buildRuntime(ctx); err != nil {
		t.Fatal(err)
	}
	pg := service.GetManagedDataConnector(1).(*postgresqlbun.Connector)
	objects := service.GetManagedDataConnector(2)
	defer pg.Stop(ctx)
	defer objects.Stop(ctx)
	if err := pg.Start(ctx); err != nil {
		t.Fatal(err)
	}
	if err := objects.Start(ctx); err != nil {
		t.Fatal(err)
	}
	// Disposable fixture provisioning, outside graph handlers and startup.
	if _, err := pg.DB().ExecContext(ctx, "CREATE TABLE query_example_items (key text PRIMARY KEY, value bytea NOT NULL)"); err != nil {
		t.Fatal(err)
	}
	awsConfig, err := awscfg.LoadDefaultConfig(ctx, awscfg.WithRegion("eu-west-1"))
	if err != nil {
		t.Fatal(err)
	}
	setup := s3.NewFromConfig(awsConfig, func(options *s3.Options) {
		options.BaseEndpoint = aws.String(cfg.DataConnectors.Objects.Address)
		options.UsePathStyle = true
	})
	if _, err := setup.CreateBucket(ctx, &s3.CreateBucketInput{Bucket: aws.String("query-example"), CreateBucketConfiguration: &s3types.CreateBucketConfiguration{LocationConstraint: s3types.BucketLocationConstraintEuWest1}}); err != nil {
		t.Fatal(err)
	}

	call := func(entry runtime.SubStream[*types.StorageRequest, *types.StorageResult], key string, value []byte, requestID string) ([]*types.StorageResult, error) {
		var results []*types.StorageResult
		err := entry.Consume(ctx, &types.StorageRequest{RequestID: requestID, Key: key, Value: value}, runtime.SubStreamCollectorFunc[*types.StorageResult](func(_ context.Context, result *types.StorageResult) bool {
			results = append(results, result)
			return result.Kind == "completed"
		}))
		if err != nil {
			return nil, err
		}
		if len(results) == 0 || results[len(results)-1].Kind != "completed" {
			return nil, fmt.Errorf("missing completion")
		}
		for _, result := range results {
			if result.RequestID != requestID {
				return nil, fmt.Errorf("request identity mixed")
			}
		}
		return results[:len(results)-1], nil
	}
	run := func(entry runtime.SubStream[*types.StorageRequest, *types.StorageResult], key string, value []byte) []*types.StorageResult {
		result, err := call(entry, key, value, "request")
		if err != nil {
			t.Fatal(err)
		}
		return result
	}
	payload := bytes.Repeat([]byte{0, 1, 255, 39}, 65600)
	key := "key'; quoted"
	returningKey := "returning-'key"
	if got := run(service.ReturningRequest(), returningKey, payload); len(got) != 1 || !bytes.Equal(got[0].Value, payload) {
		t.Fatal("RETURNING result mismatch")
	}
	if got := run(service.RowsRequest(), returningKey, nil); len(got) != 1 || !bytes.Equal(got[0].Value, payload) {
		t.Fatal("RETURNING write was not persisted")
	}
	if got := run(service.RowsRequest(), key, nil); len(got) != 0 {
		t.Fatal("empty rows")
	}
	if got := run(service.ExecuteRequest(), key, payload); len(got) != 1 || string(got[0].Value) != "1" {
		t.Fatal("command outcome")
	}
	if got := run(service.RowsRequest(), key, nil); len(got) != 1 || !bytes.Equal(got[0].Value, payload) {
		t.Fatal("binary SQL value changed")
	}
	run(service.ExecuteRequest(), key, []byte("updated\x00"))
	if got := run(service.RowsRequest(), key, nil); len(got) != 1 || string(got[0].Value) != "updated\x00" {
		t.Fatal("upsert update")
	}
	run(service.PutObjectRequest(), "object", payload)
	meta := run(service.HeadObjectRequest(), "object", nil)
	var metadata struct {
		Size int `json:"size"`
	}
	if len(meta) != 1 {
		t.Fatal("metadata result")
	}
	if err := json.Unmarshal(meta[0].Value, &metadata); err != nil || metadata.Size != len(payload) {
		t.Fatal("object size", err)
	}
	join := func(results []*types.StorageResult) []byte {
		var value []byte
		for _, r := range results {
			value = append(value, r.Value...)
		}
		return value
	}
	if !bytes.Equal(join(run(service.GetObjectRequest(), "object", nil)), payload) {
		t.Fatal("object changed")
	}
	pages := run(service.ListObjectsRequest(), "object", nil)
	var entries []struct {
		Key  string `json:"key"`
		Size int    `json:"size"`
	}
	if len(pages) != 1 {
		t.Fatal("listing page")
	}
	if err := json.Unmarshal(pages[0].Value, &entries); err != nil || len(entries) != 1 || entries[0].Key != "object" || entries[0].Size != len(payload) {
		t.Fatal("listing", err)
	}
	var wg sync.WaitGroup
	failures := make(chan error, 4)
	for i := range 4 {
		wg.Go(func() {
			got, err := call(service.GetObjectRequest(), "object", nil, fmt.Sprintf("parallel-%d", i))
			if err != nil {
				failures <- err
			} else if !bytes.Equal(join(got), payload) {
				failures <- fmt.Errorf("parallel object changed")
			}
		})
	}
	wg.Wait()
	close(failures)
	for err := range failures {
		t.Error(err)
	}
	run(service.PutObjectRequest(), "empty", nil)
	if got := run(service.GetObjectRequest(), "empty", nil); len(got) != 0 {
		t.Fatal("empty object")
	}
	rowsObserver := &observedRows{ended: make(chan error, 8)}
	getObserver := &observedGet{ended: make(chan error, 8)}
	if _, err := functions.MakeEndpointConsumerRowsQuery(service.streams.rowsStorageOperation, pg.DB(), rowsObserver); err != nil {
		t.Fatal(err)
	}
	if _, err := functions.MakeEndpointConsumerGetObjectQuery(service.streams.getObjectStorageOperation, objects.(*s3aws.Connector), getObserver); err != nil {
		t.Fatal(err)
	}
	failed := func(entry runtime.SubStream[*types.StorageRequest, *types.StorageResult], key string, ended <-chan error, cancelLocked bool) error {
		requestCtx, cancelRequest := context.WithTimeout(ctx, 3*time.Second)
		defer cancelRequest()
		done := make(chan error, 1)
		var received []*types.StorageResult
		go func() {
			done <- entry.Consume(requestCtx, &types.StorageRequest{RequestID: "failure", Key: key}, runtime.SubStreamCollectorFunc[*types.StorageResult](func(_ context.Context, result *types.StorageResult) bool {
				received = append(received, result)
				return result.Kind == "completed"
			}))
		}()
		if cancelLocked {
			until := time.Now().Add(time.Second)
			waiting := 0
			for time.Now().Before(until) {
				err := pg.DB().NewRaw("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock' AND state = 'active'").Scan(ctx, &waiting)
				if err != nil {
					t.Fatal(err)
				}
				if waiting > 0 {
					break
				}
				time.Sleep(10 * time.Millisecond)
			}
			if waiting == 0 {
				t.Fatal("SQL did not reach lock")
			}
			cancelRequest()
		}
		var outcome error
		select {
		case outcome = <-ended:
		case <-ctx.Done():
			t.Fatal("handler did not finalize")
		}
		cancelRequest()
		<-done
		if outcome == nil {
			t.Fatal("native failure reported success")
		}
		for _, result := range received {
			if result.Kind == "completed" {
				t.Fatal("false completion")
			}
		}
		return outcome
	}
	var apiError smithy.APIError
	if err := failed(service.GetObjectRequest(), "not-present", getObserver.ended, false); !errors.As(err, &apiError) || apiError.ErrorCode() != "NoSuchKey" {
		t.Fatalf("expected NoSuchKey: %v", err)
	}
	if _, err := pg.DB().ExecContext(ctx, "ALTER TABLE query_example_items RENAME TO query_example_hidden"); err != nil {
		t.Fatal(err)
	}
	sqlFailure := failed(service.RowsRequest(), key, rowsObserver.ended, false)
	if _, err := pg.DB().ExecContext(ctx, "ALTER TABLE query_example_hidden RENAME TO query_example_items"); err != nil {
		t.Fatal(err)
	}
	var sqlError interface{ SQLState() string }
	if !errors.As(sqlFailure, &sqlError) || sqlError.SQLState() != "42P01" {
		t.Fatalf("expected SQLSTATE 42P01: %v", sqlFailure)
	}
	transaction, err := pg.DB().BeginTx(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := transaction.ExecContext(ctx, "LOCK TABLE query_example_items IN ACCESS EXCLUSIVE MODE"); err != nil {
		t.Fatal(err)
	}
	cancellation := failed(service.RowsRequest(), key, rowsObserver.ended, true)
	if err := transaction.Rollback(); err != nil {
		t.Fatal(err)
	}
	if !errors.Is(cancellation, context.Canceled) {
		t.Fatalf("expected cancellation: %v", cancellation)
	}
	if got := run(service.RowsRequest(), key, nil); len(got) != 1 || string(got[0].Value) != "updated\x00" {
		t.Fatal("pool not reusable")
	}
	if !bytes.Equal(join(run(service.GetObjectRequest(), "object", nil)), payload) {
		t.Fatal("S3 not reusable")
	}
	run(service.DeleteObjectRequest(), "object", nil)
	pages = run(service.ListObjectsRequest(), "object", nil)
	if len(pages) != 1 || string(pages[0].Value) != "[]" {
		t.Fatal("deleted object remains")
	}
}
