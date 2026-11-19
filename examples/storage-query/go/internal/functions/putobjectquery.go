package functions

import (
	"bytes"
	"context"
	"github.com/aws/aws-sdk-go-v2/aws"

	"example.com/storage-query/storageworker/internal/types"
	"github.com/aws/aws-sdk-go-v2/service/s3"

	"github.com/gorundebug/servicelib/dataquery/s3aws"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type putObjectQueryHandler = s3aws.PutObjectHandler[PutObjectQueryHandlerState, *types.StorageRequest, *types.StorageResult, error]

var _ putObjectQueryHandler = (*PutObjectQuery)(nil)

type PutObjectQueryHandlerState = *requestState
type PutObjectQuery struct{}

func MakeEndpointConsumerPutObjectQuery(stream runtime.TypedQueryStream[*types.StorageRequest, *types.StorageResult, error], client s3aws.PutObjectClient, handler putObjectQueryHandler) (runtime.Consumer[*types.StorageRequest], error) {
	return s3aws.MakePutObjectEndpointConsumer[PutObjectQueryHandlerState, *types.StorageRequest, *types.StorageResult, error](stream, client, handler)
}
func (ep *PutObjectQuery) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, PutObjectQueryHandlerState, error) {
	return ctx, &requestState{}, nil
}
func (ep *PutObjectQuery) BuildRequest(ctx context.Context, state PutObjectQueryHandlerState, value *types.StorageRequest) (*s3.PutObjectInput, error) {
	state.requestID = value.RequestID
	return &s3.PutObjectInput{Bucket: aws.String("query-example"), Key: aws.String(value.Key), Body: bytes.NewReader(value.Value)}, nil
}
func (ep *PutObjectQuery) HandleResult(ctx context.Context, state PutObjectQueryHandlerState, result *s3.PutObjectOutput, out runtime.Collect[*types.StorageResult]) error {
	out.Out(ctx, &types.StorageResult{RequestID: state.requestID, Kind: "command", Value: []byte(aws.ToString(result.ETag))})
	return nil
}

// Native resources close before EndRequest. out is the ordinary result collector.
func (ep *PutObjectQuery) EndRequest(ctx context.Context, _ runtime.Stream, state PutObjectQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], errors runtime.Collect[error]) {
	finishQuery(ctx, state, err, out, errors)
}
func MakePutObjectQuery(ctx context.Context, env environment.ServiceEnvironment) (*PutObjectQuery, error) {
	return &PutObjectQuery{}, nil
}
