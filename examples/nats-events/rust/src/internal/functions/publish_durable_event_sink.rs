// User-owned canonical endpoint. Publication outcomes return through the graph.
use servicelib::{MessageContext, Payload, runtime::environment::{RuntimeEnvironment, RuntimeResult}};
use servicelib::datasink::nats as endpoint;
use crate::internal::types::{Event, PublicationOutcome};
#[derive(Clone, Default)]
pub struct PublishDurableEventSink;
#[async_trait::async_trait]
impl endpoint::EndpointHandler<(), Event, PublicationOutcome, String> for PublishDurableEventSink {
    async fn on_error(&self, context: MessageContext, stream: endpoint::StreamContext<Event, PublicationOutcome, String>, error: endpoint::HandlerError) { stream.error_collect(context, error.to_string()).await; }
    fn get_stream_id(&self, context: &MessageContext, value: &Event) -> String { context.stream_id().unwrap_or(&value.id).to_owned() }
    async fn begin_request(&self, context: MessageContext, _: endpoint::StreamContext<Event, PublicationOutcome, String>) -> (MessageContext, ()) { (context, ()) }
    async fn consume_message(&self, _: MessageContext, _: endpoint::StreamContext<Event, PublicationOutcome, String>, _: &mut (), value: Payload<Event>, message: &mut endpoint::SinkMessage<PublicationOutcome, String>) -> endpoint::HandlerResult {
        message.payload = serde_json::to_vec(&*value)?;
        let id = value.id.clone();
        message.send(move |result| PublicationOutcome { event_id: id, accepted: result.is_ok(), reason: result.err().map(|e|e.to_string()).unwrap_or_default() }).await?;
        Ok(())
    }
    async fn end_request(&self, _: MessageContext, _: endpoint::StreamContext<Event, PublicationOutcome, String>, result: &endpoint::HandlerResult, _: ()) { if let Err(error) = result { eprintln!("sink: {error}"); } }
}
pub async fn make_publish_durable_event_sink(_: MessageContext, _: RuntimeEnvironment) -> RuntimeResult<PublishDurableEventSink> { Ok(PublishDurableEventSink) }
