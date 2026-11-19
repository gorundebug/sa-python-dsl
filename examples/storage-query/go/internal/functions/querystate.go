package functions

import (
	"context"
	"example.com/storage-query/storageworker/internal/types"
	"github.com/gorundebug/servicelib/runtime"
)

// Allocated by BeginRequest, never shared across invocations.
type requestState struct{ requestID string }

func finishQuery(ctx context.Context, state *requestState, err error, out runtime.Collect[*types.StorageResult], errors runtime.Collect[error]) {
	if err != nil {
		errors.Out(ctx, err)
		return
	}
	out.Out(ctx, &types.StorageResult{RequestID: state.requestID, Kind: "completed"})
}
