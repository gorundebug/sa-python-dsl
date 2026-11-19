package functions

import (
	"context"
	"encoding/json"
	"github.com/aws/aws-sdk-go-v2/aws"

	"example.com/storage-query/storageworker/internal/types"
	"github.com/aws/aws-sdk-go-v2/service/s3"

	"github.com/gorundebug/servicelib/dataquery/s3aws"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type listObjectsQueryHandler = s3aws.ListObjectsHandler[ListObjectsQueryHandlerState, *types.StorageRequest, *types.StorageResult, error]

var _ listObjectsQueryHandler = (*ListObjectsQuery)(nil)

type ListObjectsQueryHandlerState = *requestState
type ListObjectsQuery struct{}

func MakeEndpointConsumerListObjectsQuery(stream runtime.TypedQueryStream[*types.StorageRequest, *types.StorageResult, error], client s3aws.ListObjectsClient, handler listObjectsQueryHandler) (runtime.Consumer[*types.StorageRequest], error) {
	return s3aws.MakeListObjectsEndpointConsumer[ListObjectsQueryHandlerState, *types.StorageRequest, *types.StorageResult, error](stream, client, handler)
}
func (ep *ListObjectsQuery) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, ListObjectsQueryHandlerState, error) {
	return ctx, &requestState{}, nil
}
func (ep *ListObjectsQuery) BuildRequest(ctx context.Context, state ListObjectsQueryHandlerState, value *types.StorageRequest) (*s3.ListObjectsV2Input, error) {
	state.requestID = value.RequestID
	return &s3.ListObjectsV2Input{Bucket: aws.String("query-example"), Prefix: aws.String(value.Key)}, nil
}
func (ep *ListObjectsQuery) HandleResult(ctx context.Context, state ListObjectsQueryHandlerState, result *s3.ListObjectsV2Output, out runtime.Collect[*types.StorageResult]) error {
	type entry struct {
		Key  string `json:"key"`
		Size int64  `json:"size"`
	}
	entries := make([]entry, 0, len(result.Contents))
	for _, item := range result.Contents {
		entries = append(entries, entry{aws.ToString(item.Key), aws.ToInt64(item.Size)})
	}
	payload, err := json.Marshal(entries)
	if err != nil {
		return err
	}
	out.Out(ctx, &types.StorageResult{RequestID: state.requestID, Kind: "page", Value: payload})
	return nil
}

// Native resources close before EndRequest. out is the ordinary result collector.
func (ep *ListObjectsQuery) EndRequest(ctx context.Context, _ runtime.Stream, state ListObjectsQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], errors runtime.Collect[error]) {
	finishQuery(ctx, state, err, out, errors)
}
func MakeListObjectsQuery(ctx context.Context, env environment.ServiceEnvironment) (*ListObjectsQuery, error) {
	return &ListObjectsQuery{}, nil
}
