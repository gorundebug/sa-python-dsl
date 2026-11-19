use sqlx::Row;
use sqlx::Arguments;
// User-owned business implementation. Preserve this file during merge.
use servicelib::dataquery as endpoint;

use crate::internal::types::StorageRequest;
use crate::internal::types::StorageResult;

#[derive(Clone, Default)]
pub struct RowsQuery;

#[async_trait::async_trait]
impl endpoint::postgresqlsqlx::QueryBuilder<String, StorageRequest> for RowsQuery {

    async fn build_query(&self, _context: servicelib::MessageContext, _state: &mut String, _value: servicelib::Payload<StorageRequest>) -> std::result::Result<endpoint::postgresqlsqlx::Query, endpoint::HandlerError> {
        *_state = _value.request_id.clone();
        let mut arguments = sqlx::postgres::PgArguments::default();
        arguments.add(_value.key.clone())?;
        Ok(endpoint::postgresqlsqlx::Query { sql: "SELECT value FROM query_example_items WHERE key = $1".into(), arguments })
    }

}

#[async_trait::async_trait]
impl endpoint::postgresqlsqlx::RowsHandler<String, StorageRequest, StorageResult> for RowsQuery {

    async fn handle_row(&self, _context: servicelib::MessageContext, _state: &mut String, _row: sqlx::postgres::PgRow, _out: &endpoint::Collector<StorageResult>) -> endpoint::HandlerResult {
        let value = _row.try_get::<Vec<u8>, _>("value")?;
        _out.collect(_context, StorageResult { request_id: _state.clone(), kind: "record".into(), value }).await;
        Ok(())
    }

}

#[async_trait::async_trait]
impl endpoint::EndpointHandler<String, StorageResult, String> for RowsQuery {

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

pub async fn make_rows_query(
    _context: servicelib::MessageContext,
    _environment: servicelib::runtime::environment::RuntimeEnvironment,
) -> servicelib::runtime::environment::RuntimeResult<RowsQuery> {
    Ok(RowsQuery)
}
