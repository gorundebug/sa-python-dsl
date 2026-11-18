use serde::{Deserialize, Serialize};
#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct Event {
    #[serde(rename = "ID")]
    pub id: String,
    #[serde(rename = "Value")]
    pub value: String,
}
