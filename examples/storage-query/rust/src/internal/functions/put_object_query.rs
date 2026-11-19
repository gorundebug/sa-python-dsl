// User-owned business implementation. Preserve this file during merge.
use servicelib::dataquery as endpoint;

use crate::internal::types::StorageRequest;
use crate::internal::types::StorageResult;

#[derive(Clone, Default)]
pub struct PutObjectQuery;

#[async_trait::async_trait]
impl endpoint::s3aws::PutObjectHandler<String, StorageRequest, StorageResult> for PutObjectQuery {

    async fn build_request(&self, _context: servicelib::MessageContext, _state: &mut String, _value: servicelib::Payload<StorageRequest>, _client: &aws_sdk_s3::Client) -> std::result::Result<aws_sdk_s3::operation::put_object::builders::PutObjectFluentBuilder, endpoint::HandlerError> {
        *_state = _value.request_id.clone();
        Ok(_client.put_object().bucket("query-example").key(&_value.key).body(aws_sdk_s3::primitives::ByteStream::from(_value.value.clone())))
    }

    async fn handle_result(&self, _context: servicelib::MessageContext, _state: &mut String, _result: &mut aws_sdk_s3::operation::put_object::PutObjectOutput, _out: &endpoint::Collector<StorageResult>) -> endpoint::HandlerResult {
        let value = _result.e_tag().unwrap_or("").as_bytes().to_vec();
        _out.collect(_context, StorageResult { request_id: _state.clone(), kind: "command".into(), value }).await;
        Ok(())
    }

}

#[async_trait::async_trait]
impl endpoint::EndpointHandler<String, StorageResult, String> for PutObjectQuery {

    async fn begin_request(&self, _context: servicelib::MessageContext, _stream: &dyn servicelib::runtime::common::RuntimeStream) -> std::result::Result<endpoint::BeginRequest<String>, endpoint::HandlerError> {
        Ok(endpoint::BeginRequest { context: _context, state: String::new(), error: None })
    }

    async fn end_request(&self, _context: servicelib::MessageContext, _stream: &dyn servicelib::runtime::common::RuntimeStream, _state: Option<String>, _result: &endpoint::HandlerResult, _out: &endpoint::Collector<StorageResult>, _errors: &endpoint::Collector<String>) {
        match _result {
            Err(error) => _errors.collect(_context, error.to_string()).await,
            Ok(()) => {
                if let Some(request_id) = _state {
                    _out.collect(_context, StorageResult { request_id, kind: "completed".into(), value: Vec::new() }).await;
                }
            }
        }
    }

}

pub async fn make_put_object_query(
    _context: servicelib::MessageContext,
    _environment: servicelib::runtime::environment::RuntimeEnvironment,
) -> servicelib::runtime::environment::RuntimeResult<PutObjectQuery> {
    Ok(PutObjectQuery)
}
