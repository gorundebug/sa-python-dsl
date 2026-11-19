package functions

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"testing"

	"example.com/storage-query/storageworker/internal/types"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/gorundebug/servicelib/runtime"
)

type exampleErrors struct {
	runtime.TypedConsumedStream[error]
	values []error
}

func (s *exampleErrors) Consume(_ context.Context, err error) { s.values = append(s.values, err) }

type exampleStream struct {
	runtime.TypedQueryStream[*types.StorageRequest, *types.StorageResult, error]
	values []*types.StorageResult
	errors exampleErrors
}

func (s *exampleStream) SetQueryConsumer(runtime.Consumer[*types.StorageRequest]) {}
func (s *exampleStream) ConsumeResult(_ context.Context, result *types.StorageResult) {
	s.values = append(s.values, result)
}
func (s *exampleStream) GetErrorStream() runtime.TypedConsumedStream[error] { return &s.errors }

type exampleTransport func(*http.Request) (*http.Response, error)

func (f exampleTransport) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

// Executes the real AWS serializer/parser and SDK consumer with in-process HTTP.
// This is not an S3 server interoperability test.
func TestExampleS3Operations(t *testing.T) {
	transport := exampleTransport(func(r *http.Request) (*http.Response, error) {
		body := "payload"
		header := make(http.Header)
		status := 200
		if r.URL.Query().Get("list-type") == "2" {
			header.Set("Content-Type", "application/xml")
			if r.URL.Query().Get("continuation-token") == "next" {
				body = `<ListBucketResult><IsTruncated>false</IsTruncated></ListBucketResult>`
			} else {
				body = `<ListBucketResult><IsTruncated>true</IsTruncated><NextContinuationToken>next</NextContinuationToken><Contents><Key>key1</Key><Size>7</Size></Contents></ListBucketResult>`
			}
		} else {
			if r.URL.Path != "/query-example/key" {
				t.Errorf("unexpected path %s", r.URL.Path)
			}
			switch r.Method {
			case "HEAD":
				body = ""
				header.Set("Content-Length", "7")
			case "PUT":
				value, err := io.ReadAll(r.Body)
				if err != nil || string(value) != "payload" {
					t.Errorf("upload: %q, %v", value, err)
				}
				body = ""
				header.Set("ETag", "tag")
			case "DELETE":
				body = ""
				status = 204
			}
		}
		return &http.Response{StatusCode: status, Header: header, Body: io.NopCloser(strings.NewReader(body)), Request: r}, nil
	})
	client := s3.New(s3.Options{Region: "eu-west-1", BaseEndpoint: aws.String("https://s3.example.invalid"), UsePathStyle: true, Credentials: aws.AnonymousCredentials{}, HTTPClient: &http.Client{Transport: transport}})
	cases := []struct {
		name  string
		bind  func(*exampleStream) (runtime.Consumer[*types.StorageRequest], error)
		count int
	}{
		{"get", func(s *exampleStream) (runtime.Consumer[*types.StorageRequest], error) {
			return MakeEndpointConsumerGetObjectQuery(s, client, &GetObjectQuery{})
		}, 2},
		{"head", func(s *exampleStream) (runtime.Consumer[*types.StorageRequest], error) {
			return MakeEndpointConsumerHeadObjectQuery(s, client, &HeadObjectQuery{})
		}, 2},
		{"list", func(s *exampleStream) (runtime.Consumer[*types.StorageRequest], error) {
			return MakeEndpointConsumerListObjectsQuery(s, client, &ListObjectsQuery{})
		}, 3},
		{"put", func(s *exampleStream) (runtime.Consumer[*types.StorageRequest], error) {
			return MakeEndpointConsumerPutObjectQuery(s, client, &PutObjectQuery{})
		}, 2},
		{"delete", func(s *exampleStream) (runtime.Consumer[*types.StorageRequest], error) {
			return MakeEndpointConsumerDeleteObjectQuery(s, client, &DeleteObjectQuery{})
		}, 2},
	}
	for _, tt := range cases {
		t.Run(tt.name, func(t *testing.T) {
			stream := &exampleStream{}
			consumer, err := tt.bind(stream)
			if err != nil {
				t.Fatal(err)
			}
			consumer.Consume(t.Context(), &types.StorageRequest{RequestID: "request", Key: "key", Value: []byte("payload")})
			if len(stream.errors.values) != 0 {
				t.Fatal(stream.errors.values)
			}
			if len(stream.values) != tt.count {
				t.Fatalf("results: %+v", stream.values)
			}
			for _, v := range stream.values {
				if v.RequestID != "request" {
					t.Fatalf("lost request identity: %+v", v)
				}
			}
			if stream.values[tt.count-1].Kind != "completed" {
				t.Fatal("missing completion")
			}
			if tt.name == "get" && string(stream.values[0].Value) != "payload" {
				t.Fatal("incorrect object")
			}
			if tt.name == "list" && string(stream.values[1].Value) != "[]" {
				t.Fatal("empty final page lost")
			}
		})
	}
}

func TestExampleFailureDoesNotEmitCompletion(t *testing.T) {
	stream := &exampleStream{}
	err := fmt.Errorf("request failed")
	finishQuery(t.Context(), nil, err,
		runtime.CollectFunc[*types.StorageResult](stream.ConsumeResult),
		runtime.CollectFunc[error](stream.errors.Consume))
	if len(stream.values) != 0 || len(stream.errors.values) != 1 || stream.errors.values[0] != err {
		t.Fatal("incorrect failure result")
	}
}
