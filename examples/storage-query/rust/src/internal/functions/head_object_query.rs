// User-owned business implementation. Preserve this file during merge.
use servicelib::dataquery as endpoint;

use crate::internal::types::StorageRequest;
use crate::internal::types::StorageResult;

#[derive(Clone, Default)]
pub struct HeadObjectQuery;

#[async_trait::async_trait]
impl endpoint::s3aws::HeadObjectHandler<String, StorageRequest, StorageResult> for HeadObjectQuery {

    async fn build_request(&self, _context: servicelib::MessageContext, _state: &mut String, _value: servicelib::Payload<StorageRequest>, _client: &aws_sdk_s3::Client) -> std::result::Result<aws_sdk_s3::operation::head_object::builders::HeadObjectFluentBuilder, endpoint::HandlerError> {
        *_state = _value.request_id.clone();
        Ok(_client.head_object().bucket("query-example").key(&_value.key))
    }

    async fn handle_result(&self, _context: servicelib::MessageContext, _state: &mut String, _result: &mut aws_sdk_s3::operation::head_object::HeadObjectOutput, _out: &endpoint::Collector<StorageResult>) -> endpoint::HandlerResult {
        let value = serde_json::to_vec(&serde_json::json!({"size": _result.content_length(), "etag": _result.e_tag().unwrap_or("")}))?;
        _out.collect(_context, StorageResult { request_id: _state.clone(), kind: "object".into(), value }).await;
        Ok(())
    }

}

#[async_trait::async_trait]
impl endpoint::EndpointHandler<String, StorageResult, String> for HeadObjectQuery {

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

pub async fn make_head_object_query(
    _context: servicelib::MessageContext,
    _environment: servicelib::runtime::environment::RuntimeEnvironment,
) -> servicelib::runtime::environment::RuntimeResult<HeadObjectQuery> {
    Ok(HeadObjectQuery)
}
