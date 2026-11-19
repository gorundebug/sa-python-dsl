package functions

import (
	"context"
	"github.com/aws/aws-sdk-go-v2/aws"
	"io"

	"example.com/storage-query/storageworker/internal/types"
	"github.com/aws/aws-sdk-go-v2/service/s3"

	"github.com/gorundebug/servicelib/dataquery/s3aws"
	"github.com/gorundebug/servicelib/runtime"
	"github.com/gorundebug/servicelib/runtime/environment"
)

type getObjectQueryHandler = s3aws.GetObjectHandler[GetObjectQueryHandlerState, *types.StorageRequest, *types.StorageResult, error]

var _ getObjectQueryHandler = (*GetObjectQuery)(nil)

type GetObjectQueryHandlerState = *requestState
type GetObjectQuery struct{}

func MakeEndpointConsumerGetObjectQuery(stream runtime.TypedQueryStream[*types.StorageRequest, *types.StorageResult, error], client s3aws.GetObjectClient, handler getObjectQueryHandler) (runtime.Consumer[*types.StorageRequest], error) {
	return s3aws.MakeGetObjectEndpointConsumer[GetObjectQueryHandlerState, *types.StorageRequest, *types.StorageResult, error](stream, client, handler)
}
func (ep *GetObjectQuery) BeginRequest(ctx context.Context, _ runtime.Stream) (context.Context, GetObjectQueryHandlerState, error) {
	return ctx, &requestState{}, nil
}
func (ep *GetObjectQuery) BuildRequest(ctx context.Context, state GetObjectQueryHandlerState, value *types.StorageRequest) (*s3.GetObjectInput, error) {
	state.requestID = value.RequestID
	return &s3.GetObjectInput{Bucket: aws.String("query-example"), Key: aws.String(value.Key)}, nil
}
func (ep *GetObjectQuery) HandleResult(ctx context.Context, state GetObjectQueryHandlerState, result *s3.GetObjectOutput, out runtime.Collect[*types.StorageResult]) error {
	buffer := make([]byte, 64*1024)
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		count, err := result.Body.Read(buffer)
		if count > 0 {
			out.Out(ctx, &types.StorageResult{RequestID: state.requestID, Kind: "object", Value: append([]byte(nil), buffer[:count]...)})
		}
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return err
		}
	}
}

// Native resources close before EndRequest. out is the ordinary result collector.
func (ep *GetObjectQuery) EndRequest(ctx context.Context, _ runtime.Stream, state GetObjectQueryHandlerState, err error, out runtime.Collect[*types.StorageResult], errors runtime.Collect[error]) {
	finishQuery(ctx, state, err, out, errors)
}
func MakeGetObjectQuery(ctx context.Context, env environment.ServiceEnvironment) (*GetObjectQuery, error) {
	return &GetObjectQuery{}, nil
}
