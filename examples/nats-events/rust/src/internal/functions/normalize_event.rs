use crate::internal::types::Event;
#[derive(Clone, Default)]
pub struct NormalizeEvent;
impl servicelib::operators::map::MapFunction<Event, Event> for NormalizeEvent {
    async fn map(&self, context: servicelib::MessageContext, _: &dyn servicelib::runtime::common::RuntimeStream, value: &Event, out: &impl servicelib::runtime::collector::Collect<Event>) {
        out.out(context, Event { id: value.id.clone(), value: value.value.trim().to_uppercase() }).await;
    }
}
pub async fn make_normalize_event(_: servicelib::MessageContext, _: servicelib::runtime::environment::RuntimeEnvironment) -> servicelib::runtime::environment::RuntimeResult<NormalizeEvent> { Ok(NormalizeEvent) }
