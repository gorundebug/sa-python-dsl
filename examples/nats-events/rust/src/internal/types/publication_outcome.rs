use serde::{Deserialize, Serialize};
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct PublicationOutcome {
    #[serde(rename = "EventID")]
    pub event_id: String,
    #[serde(rename = "Accepted")]
    pub accepted: bool,
    #[serde(rename = "Reason")]
    pub reason: String,
}
