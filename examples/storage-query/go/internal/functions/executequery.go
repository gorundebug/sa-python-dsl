package functions

import (
	"context"
	"database/sql"
	"strconv"

	"example.com/storage-query/storageworker/internal/types"
	"github.com/uptrace/bun"

	"github.com/gorundebug/servicelib/dataquery"
	"github.com/gorundebug/servicelib/dataquery/postgresqlbun"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type executeQueryHandler = postgresqlbun.ExecHandler[ExecuteQueryHandlerState, *types.StorageRequest, *types.StorageResult, error]

var _ executeQueryHandler = (*ExecuteQuery)(nil)

type ExecuteQueryHandlerState = *requestState
type ExecuteQuery struct{}

func MakeEndpointConsumerExecuteQuery(stream runtime.TypedQueryStream[*types.StorageRequest, *types.StorageResult, error], db *bun.DB, handler executeQueryHandler, options ...dataquery.Options) (runtime.Consumer[*types.StorageRequest], error) {
	return postgresqlbun.MakeExecEndpointConsumer[ExecuteQueryHandlerState, *types.StorageRequest, *types.StorageResult, error](stream, db, handler, options...)
}

// BeginRequest creates state for this invocation, never shared between requests.
func (ep *ExecuteQuery) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, ExecuteQueryHandlerState, error) {
	return ctx, &requestState{}, nil
}

// BuildQuery builds a Bun query using request data and separate SQL parameters.
// The SDK executes it once; it never replays writes or partially emitted results.
func (ep *ExecuteQuery) BuildQuery(ctx context.Context, state ExecuteQueryHandlerState, value *types.StorageRequest, db *bun.DB) (postgresqlbun.ExecQuery, error) {
	state.requestID = value.RequestID
	return db.NewRaw("INSERT INTO query_example_items (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", value.Key, value.Value), nil
}

func (ep *ExecuteQuery) HandleResult(ctx context.Context, state ExecuteQueryHandlerState, result sql.Result, out runtime.Collect[*types.StorageResult]) error {
	count, err := result.RowsAffected()
	if err != nil {
		return err
	}
	out.Out(ctx, &types.StorageResult{RequestID: state.requestID, Kind: "command", Value: []byte(strconv.FormatInt(count, 10))})
	return nil
}

// EndRequest runs after native resources close, including on initial failure.
// out is the ordinary result collector: emit a completion value only if needed.
func (ep *ExecuteQuery) EndRequest(ctx context.Context, _ runtime.Stream, state ExecuteQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], errors runtime.Collect[error]) {
	finishQuery(ctx, state, err, out, errors)
}

func MakeExecuteQuery(ctx context.Context, env environment.ServiceEnvironment) (*ExecuteQuery, error) {
	return &ExecuteQuery{}, nil
}
