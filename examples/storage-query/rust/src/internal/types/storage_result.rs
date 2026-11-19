use serde::{Deserialize, Serialize};

/// RequestID string; Kind string (record, command, object, page, completed); Value bytes. Completion is emitted explicitly by EndRequest.
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct StorageResult {
    pub request_id: String,
    pub kind: String,
    pub value: Vec<u8>,
}
