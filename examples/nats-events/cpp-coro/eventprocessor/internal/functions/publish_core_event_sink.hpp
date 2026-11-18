#pragma once
#include <boost/json.hpp>
#include <exception>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <variant>

#include <boost/asio/awaitable.hpp>
#include <eventprocessor/internal/types/event.hpp>
#include <eventprocessor/internal/types/publication_outcome.hpp>

#include <servicelib/runtime/common.hpp>
#include <servicelib/runtime/config/endpoint_types.hpp>
#include <servicelib/runtime/environment/environment.hpp>
#include <servicelib/datasink/nats/client.hpp>

namespace nats_events::event_processor::functions {
struct PublishCoreEventSink final {
  using State = std::monostate;

  // Resumes on the application executor, never a native NATS callback thread.
  boost::asio::awaitable<void> onError(servicelib::MessageContext context, auto& stream, std::exception_ptr error) const {
    co_await stream.collectError(std::move(context), std::move(error));
    co_return;
  }
  boost::asio::awaitable<servicelib::BeginResult<State>> beginRequest(servicelib::MessageContext context, auto&) const {
    co_return servicelib::BeginResult<State>{std::move(context), {}};
  }

  boost::asio::awaitable<std::string> getStreamId(servicelib::MessageContext context, const nats_events::event_processor::types::Event&) const { co_return std::string{context.streamId()}; }
  // Set value and call send with a delivery-to-result mapping, or use
  // sendSync then out. Do not conflate ordinary results and typed errors.
  // Core confirms a server flush, not durable storage or downstream processing.
  boost::asio::awaitable<void> consumeMessage(servicelib::MessageContext, auto&, State&, const types::Event& event,
      servicelib::datasink::nats::SinkMessage<types::PublicationOutcome>& message) const {
    message.value = boost::json::serialize(boost::json::object{{"ID", event.ID}, {"Value", event.Value}});
    co_await message.send([id = event.ID](const servicelib::datasink::nats::DeliveryResult& delivery) -> boost::asio::awaitable<types::PublicationOutcome> {
      co_return types::PublicationOutcome{id, !delivery.error, delivery.error ? "publish failed" : ""};
    });
  }

  // endRequest follows handler return. Sink delivery callbacks may outlive it;
  // keep their captured state alive. Source completion is never implicit ACK.
  boost::asio::awaitable<void> endRequest(servicelib::MessageContext, auto&, std::exception_ptr, State&) const { co_return; }
};
inline boost::asio::awaitable<std::unique_ptr<PublishCoreEventSink>> MakePublishCoreEventSink(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::NatsEndpointConfig& config) {
  (void)context;
  (void)environment;
  (void)config;
  co_return std::make_unique<PublishCoreEventSink>();
}
}  // namespace nats_events::event_processor::functions