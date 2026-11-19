package functions

import (
	"context"
	"github.com/aws/aws-sdk-go-v2/aws"

	"example.com/storage-query/storageworker/internal/types"
	"github.com/aws/aws-sdk-go-v2/service/s3"

	"github.com/gorundebug/servicelib/dataquery/s3aws"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type deleteObjectQueryHandler = s3aws.DeleteObjectHandler[DeleteObjectQueryHandlerState, *types.StorageRequest, *types.StorageResult, error]

var _ deleteObjectQueryHandler = (*DeleteObjectQuery)(nil)

type DeleteObjectQueryHandlerState = *requestState
type DeleteObjectQuery struct{}

func MakeEndpointConsumerDeleteObjectQuery(stream runtime.TypedQueryStream[*types.StorageRequest, *types.StorageResult, error], client s3aws.DeleteObjectClient, handler deleteObjectQueryHandler) (runtime.Consumer[*types.StorageRequest], error) {
	return s3aws.MakeDeleteObjectEndpointConsumer[DeleteObjectQueryHandlerState, *types.StorageRequest, *types.StorageResult, error](stream, client, handler)
}
func (ep *DeleteObjectQuery) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, DeleteObjectQueryHandlerState, error) {
	return ctx, &requestState{}, nil
}
func (ep *DeleteObjectQuery) BuildRequest(ctx context.Context, state DeleteObjectQueryHandlerState, value *types.StorageRequest) (*s3.DeleteObjectInput, error) {
	state.requestID = value.RequestID
	return &s3.DeleteObjectInput{Bucket: aws.String("query-example"), Key: aws.String(value.Key)}, nil
}
func (ep *DeleteObjectQuery) HandleResult(ctx context.Context, state DeleteObjectQueryHandlerState, result *s3.DeleteObjectOutput, out runtime.Collect[*types.StorageResult]) error {
	out.Out(ctx, &types.StorageResult{RequestID: state.requestID, Kind: "command"})
	return nil
}

// Native resources close before EndRequest. out is the ordinary result collector.
func (ep *DeleteObjectQuery) EndRequest(ctx context.Context, _ runtime.Stream, state DeleteObjectQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], errors runtime.Collect[error]) {
	finishQuery(ctx, state, err, out, errors)
}
func MakeDeleteObjectQuery(ctx context.Context, env environment.ServiceEnvironment) (*DeleteObjectQuery, error) {
	return &DeleteObjectQuery{}, nil
}
