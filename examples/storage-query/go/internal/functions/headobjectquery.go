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

type headObjectQueryHandler = s3aws.HeadObjectHandler[HeadObjectQueryHandlerState, *types.StorageRequest, *types.StorageResult, error]

var _ headObjectQueryHandler = (*HeadObjectQuery)(nil)

type HeadObjectQueryHandlerState = *requestState
type HeadObjectQuery struct{}

func MakeEndpointConsumerHeadObjectQuery(stream runtime.TypedQueryStream[*types.StorageRequest, *types.StorageResult, error], client s3aws.HeadObjectClient, handler headObjectQueryHandler) (runtime.Consumer[*types.StorageRequest], error) {
	return s3aws.MakeHeadObjectEndpointConsumer[HeadObjectQueryHandlerState, *types.StorageRequest, *types.StorageResult, error](stream, client, handler)
}
func (ep *HeadObjectQuery) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, HeadObjectQueryHandlerState, error) {
	return ctx, &requestState{}, nil
}
func (ep *HeadObjectQuery) BuildRequest(ctx context.Context, state HeadObjectQueryHandlerState, value *types.StorageRequest) (*s3.HeadObjectInput, error) {
	state.requestID = value.RequestID
	return &s3.HeadObjectInput{Bucket: aws.String("query-example"), Key: aws.String(value.Key)}, nil
}
func (ep *HeadObjectQuery) HandleResult(ctx context.Context, state HeadObjectQueryHandlerState, result *s3.HeadObjectOutput, out runtime.Collect[*types.StorageResult]) error {
	payload, err := json.Marshal(struct {
		Size int64  `json:"size"`
		ETag string `json:"etag"`
	}{aws.ToInt64(result.ContentLength), aws.ToString(result.ETag)})
	if err != nil {
		return err
	}
	out.Out(ctx, &types.StorageResult{RequestID: state.requestID, Kind: "object", Value: payload})
	return nil
}

// Native resources close before EndRequest. out is the ordinary result collector.
func (ep *HeadObjectQuery) EndRequest(ctx context.Context, _ runtime.Stream, state HeadObjectQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], errors runtime.Collect[error]) {
	finishQuery(ctx, state, err, out, errors)
}
func MakeHeadObjectQuery(ctx context.Context, env environment.ServiceEnvironment) (*HeadObjectQuery, error) {
	return &HeadObjectQuery{}, nil
}
