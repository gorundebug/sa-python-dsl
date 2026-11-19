use serde::{Deserialize, Serialize};

/// RequestID string; Key string; Value bytes. Key is a bound SQL value or object key, never SQL syntax.
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct StorageRequest {
    pub request_id: String,
    pub key: String,
    pub value: Vec<u8>,
}
