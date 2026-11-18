// User-owned canonical endpoint. Generated bindings and makers are unchanged.
use std::sync::Arc;
use servicelib::{MessageContext, runtime::{datasource::StreamContext, environment::{RuntimeEnvironment, RuntimeResult}}};
use servicelib::datasource::nats as endpoint;
use crate::internal::types::{Event, PublicationOutcome};
#[derive(Clone, Default)]
pub struct ReceiveDurableEventSource;
#[async_trait::async_trait]
impl endpoint::EndpointHandler<(), Event, PublicationOutcome, String> for ReceiveDurableEventSource {
    async fn on_error(&self, context: MessageContext, stream: StreamContext<Event, PublicationOutcome, String>, error: endpoint::HandlerError) {
        stream.error_collect(context, error.to_string()).await;
    }
    async fn begin_request(&self, context: MessageContext, _: StreamContext<Event, PublicationOutcome, String>) -> endpoint::HandlerResult<(MessageContext, ())> { Ok((context, ())) }
    async fn consume_message(&self, context: MessageContext, stream: StreamContext<Event, PublicationOutcome, String>, _: Arc<tokio::sync::Mutex<()>>, message: endpoint::ConsumerMessage, result: Arc<endpoint::ResultContext<(), Event, PublicationOutcome, String>>) -> endpoint::HandlerResult {
        let event: Event = serde_json::from_slice(&message.message.payload)?;
        if event.id.is_empty() { return Err("Event ID is required".into()); }
        let weak = Arc::downgrade(&result);
        result.set_result_callback(event.id.clone(), Arc::new(move |context, stream, _, outcome| {
            let message = message.clone();
            let weak = weak.clone();
            Box::pin(async move {
                if let Some(js) = message.jetstream {
                    let settled = if outcome.accepted { js.double_ack().await }
                        else { js.ack_with(endpoint::native::jetstream::AckKind::Nak(None)).await };
                    if let Err(error) = settled { stream.error_collect(context, error.to_string()).await; }
                }
                println!("{}", serde_json::to_string(&*outcome).expect("string outcome JSON"));
                if let Some(result) = weak.upgrade() { result.done(); }
                true
            })
        }))?;
        stream.collect(context, event).await;
        Ok(())
    }
    async fn get_message_id(&self, _: &MessageContext, _: &StreamContext<Event, PublicationOutcome, String>, _: Arc<tokio::sync::Mutex<()>>, value: &PublicationOutcome) -> String { value.event_id.clone() }
    async fn end_request(&self, _: MessageContext, _: StreamContext<Event, PublicationOutcome, String>, result: &endpoint::HandlerResult, _: Arc<tokio::sync::Mutex<()>>) {
        if let Err(error) = result { eprintln!("source: {error}"); }
    }
}
pub async fn make_receive_durable_event_source(_: MessageContext, _: RuntimeEnvironment) -> RuntimeResult<ReceiveDurableEventSource> { Ok(ReceiveDurableEventSource) }
