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

type rowsQueryHandler = postgresqlbun.RowsHandler[RowsQueryHandlerState, *types.StorageRequest, *types.StorageResult, error]

var _ rowsQueryHandler = (*RowsQuery)(nil)

type RowsQueryHandlerState = *requestState
type RowsQuery struct{}

func MakeEndpointConsumerRowsQuery(stream runtime.TypedQueryStream[*types.StorageRequest, *types.StorageResult, error], db *bun.DB, handler rowsQueryHandler, options ...dataquery.Options) (runtime.Consumer[*types.StorageRequest], error) {
	return postgresqlbun.MakeRowsEndpointConsumer[RowsQueryHandlerState, *types.StorageRequest, *types.StorageResult, error](stream, db, handler, options...)
}

// BeginRequest creates state for this invocation, never shared between requests.
func (ep *RowsQuery) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, RowsQueryHandlerState, error) {
	return ctx, &requestState{}, nil
}

// BuildQuery builds a Bun query using request data and separate SQL parameters.
// The SDK executes it once; it never replays writes or partially emitted results.
func (ep *RowsQuery) BuildQuery(ctx context.Context, state RowsQueryHandlerState, value *types.StorageRequest, db *bun.DB) (postgresqlbun.RowsQuery, error) {
	state.requestID = value.RequestID
	return postgresqlbun.RawRows(db, "SELECT value FROM query_example_items WHERE key = ?", value.Key), nil
}

func (ep *RowsQuery) HandleRow(ctx context.Context, state RowsQueryHandlerState, rows *sql.Rows, db *bun.DB, out runtime.Collect[*types.StorageResult]) error {
	var value []byte
	if err := rows.Scan(&value); err != nil {
		return err
	}
	out.Out(ctx, &types.StorageResult{RequestID: state.requestID, Kind: "record", Value: value})
	return nil
}

// EndRequest runs after native resources close, including on initial failure.
// out is the ordinary result collector: emit a completion value only if needed.
func (ep *RowsQuery) EndRequest(ctx context.Context, _ runtime.Stream, state RowsQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], errors runtime.Collect[error]) {
	finishQuery(ctx, state, err, out, errors)
}

func MakeRowsQuery(ctx context.Context, env environment.ServiceEnvironment) (*RowsQuery, error) {
	return &RowsQuery{}, nil
}
