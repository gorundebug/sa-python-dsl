#pragma once
#include <boost/json.hpp>
#include <iostream>
#include <syncstream>
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
#include <servicelib/datasource/nats/client.hpp>

namespace nats_events::event_processor::functions {
struct ReceiveCoreEventSource final {
  using State = std::monostate;
  int concurrency(auto&) const noexcept { return 1; }

  // Resumes on the application executor, never a native NATS callback thread.
  boost::asio::awaitable<void> onError(servicelib::MessageContext context, auto& stream, std::exception_ptr error) const {
    co_await stream.collectError(std::move(context), std::move(error));
    co_return;
  }
  boost::asio::awaitable<servicelib::BeginResult<State>> beginRequest(servicelib::MessageContext context, auto&) const {
    co_return servicelib::BeginResult<State>{std::move(context), {}};
  }

  // Register result callbacks before collect; preserve the context and correlation ID.
  // Done finalizes graph processing. It never acknowledges a broker message.
  // Core has no ACK or replay. Calling ack on a Core message is an error.
  boost::asio::awaitable<void> consumeMessage(servicelib::MessageContext context, auto& stream, State&,
      const servicelib::nats::Message& message, auto result) const {
    const auto object = boost::json::parse(message.value()).as_object();
    types::Event event{std::string(object.at("ID").as_string()), std::string(object.at("Value").as_string())};
    result.setResultCallback(event.ID, [message](servicelib::MessageContext callbackContext, auto&, State&, const types::PublicationOutcome& outcome) -> boost::asio::awaitable<bool> {
      (void)callbackContext;
      std::osyncstream(std::cout) << boost::json::serialize(boost::json::object{{"EventID", outcome.EventID}, {"Accepted", outcome.Accepted}, {"Reason", outcome.Reason}}) << std::endl;
      co_return true;
    });
    co_await stream.collect(std::move(context), std::move(event));
    result.done();
  }
  boost::asio::awaitable<std::string> getMessageId(servicelib::MessageContext, auto&, State&, const nats_events::event_processor::types::PublicationOutcome& value) const { co_return value.EventID; }

  // endRequest follows handler return. Sink delivery callbacks may outlive it;
  // keep their captured state alive. Source completion is never implicit ACK.
  boost::asio::awaitable<void> endRequest(servicelib::MessageContext, auto&, std::exception_ptr, State&) const { co_return; }
};
inline boost::asio::awaitable<std::unique_ptr<ReceiveCoreEventSource>> MakeReceiveCoreEventSource(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::NatsEndpointConfig& config) {
  (void)context;
  (void)environment;
  (void)config;
  co_return std::make_unique<ReceiveCoreEventSource>();
}
}  // namespace nats_events::event_processor::functions