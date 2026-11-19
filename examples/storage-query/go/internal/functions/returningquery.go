package functions

import (
	"context"
	"database/sql"

	"example.com/storage-query/storageworker/internal/types"
	"github.com/uptrace/bun"

	"github.com/gorundebug/servicelib/dataquery"
	"github.com/gorundebug/servicelib/dataquery/postgresqlbun"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type returningQueryHandler = postgresqlbun.RowsHandler[ReturningQueryHandlerState, *types.StorageRequest, *types.StorageResult, error]

var _ returningQueryHandler = (*ReturningQuery)(nil)

type ReturningQueryHandlerState = *requestState
type ReturningQuery struct{}

func MakeEndpointConsumerReturningQuery(stream runtime.TypedQueryStream[*types.StorageRequest, *types.StorageResult, error], db *bun.DB, handler returningQueryHandler, options ...dataquery.Options) (runtime.Consumer[*types.StorageRequest], error) {
	return postgresqlbun.MakeRowsEndpointConsumer[ReturningQueryHandlerState, *types.StorageRequest, *types.StorageResult, error](stream, db, handler, options...)
}

// BeginRequest creates state for this invocation, never shared between requests.
func (ep *ReturningQuery) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, ReturningQueryHandlerState, error) {
	return ctx, &requestState{}, nil
}

// BuildQuery builds a Bun query using request data and separate SQL parameters.
// The SDK executes it once; it never replays writes or partially emitted results.
func (ep *ReturningQuery) BuildQuery(ctx context.Context, state ReturningQueryHandlerState, value *types.StorageRequest, db *bun.DB) (postgresqlbun.RowsQuery, error) {
	state.requestID = value.RequestID
	return postgresqlbun.RawRows(db, "INSERT INTO query_example_items (key, value) VALUES (?, ?) RETURNING value", value.Key, value.Value), nil
}

func (ep *ReturningQuery) HandleRow(ctx context.Context, state ReturningQueryHandlerState, rows *sql.Rows, db *bun.DB, out runtime.Collect[*types.StorageResult]) error {
	var value []byte
	if err := rows.Scan(&value); err != nil {
		return err
	}
	out.Out(ctx, &types.StorageResult{RequestID: state.requestID, Kind: "record", Value: value})
	return nil
}

// EndRequest runs after native resources close, including on initial failure.
// out is the ordinary result collector: emit a completion value only if needed.
func (ep *ReturningQuery) EndRequest(ctx context.Context, _ runtime.Stream, state ReturningQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], errors runtime.Collect[error]) {
	finishQuery(ctx, state, err, out, errors)
}

func MakeReturningQuery(ctx context.Context, env environment.ServiceEnvironment) (*ReturningQuery, error) {
	return &ReturningQuery{}, nil
}
