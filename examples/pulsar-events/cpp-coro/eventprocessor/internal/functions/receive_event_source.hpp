#pragma once
#include <boost/json.hpp>
#include <exception>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <syncstream>
#include <utility>
#include <variant>

#include <boost/asio/awaitable.hpp>
#include <eventprocessor/internal/types/event.hpp>
#include <eventprocessor/internal/types/publication_outcome.hpp>

#include <servicelib/datasource/pulsar/client.hpp>
#include <servicelib/runtime/common.hpp>
#include <servicelib/runtime/config/endpoint_types.hpp>
#include <servicelib/runtime/environment/environment.hpp>

namespace pulsar_events::event_processor::functions {
struct ReceiveEventSource final {
  using State = std::monostate;
  int concurrency(auto &) const noexcept { return 1; }

  // Resumes on the application executor, never a native Pulsar callback thread.
  boost::asio::awaitable<void> onError(servicelib::MessageContext context,
                                       auto &stream,
                                       std::exception_ptr error) const {
    co_await stream.collectError(std::move(context), std::move(error));
    co_return;
  }
  boost::asio::awaitable<servicelib::BeginResult<State>>
  beginRequest(servicelib::MessageContext context, auto &) const {
    co_return servicelib::BeginResult<State>{std::move(context), {}};
  }

  // Register result callbacks before collect; preserve the context and
  // correlation ID. Done finalizes graph processing. It never acknowledges a
  // broker message. Individually ACK only a correlated accepted publication
  // with native MessageId. Retain the copyable native message for callbacks.
  // Processing must be idempotent.
  boost::asio::awaitable<void>
  consumeMessage(servicelib::MessageContext context, auto &stream, State &,
                 const servicelib::pulsar::Message &message,
                 auto result) const {
    const auto object =
        boost::json::parse(message.native().getDataAsString()).as_object();
    types::Event event{std::string(object.at("ID").as_string()),
                       std::string(object.at("Value").as_string())};
    result.setResultCallback(
        event.ID,
        [message, result](servicelib::MessageContext callbackContext, auto &,
                          State &,
                          const types::PublicationOutcome &outcome) mutable
            -> boost::asio::awaitable<bool> {
          if (outcome.Accepted && !outcome.MessageID.empty())
            co_await message.ack(callbackContext);
          // Failed publications remain unacknowledged; no implicit retry here.
          std::osyncstream(std::cout)
              << boost::json::serialize(
                     boost::json::object{{"EventID", outcome.EventID},
                                         {"MessageID", outcome.MessageID},
                                         {"Accepted", outcome.Accepted},
                                         {"Reason", outcome.Reason}})
              << std::endl;
          result.done();
          co_return true;
        });
    co_await stream.collect(std::move(context), std::move(event));
  }
  boost::asio::awaitable<std::string>
  getMessageId(servicelib::MessageContext, auto &, State &,
               const pulsar_events::event_processor::types::PublicationOutcome
                   &value) const {
    co_return value.EventID;
  }

  // endRequest follows handler return. Sink delivery callbacks may outlive it;
  // keep their captured state alive. Source completion is never implicit ACK.
  boost::asio::awaitable<void> endRequest(servicelib::MessageContext, auto &,
                                          std::exception_ptr, State &) const {
    co_return;
  }
};
inline boost::asio::awaitable<std::unique_ptr<ReceiveEventSource>>
MakeReceiveEventSource(servicelib::Context context,
                       servicelib::IServiceEnvironment &environment,
                       const servicelib::config::PulsarEndpointConfig &config) {
  (void)context;
  (void)environment;
  (void)config;
  co_return std::make_unique<ReceiveEventSource>();
}
} // namespace pulsar_events::event_processor::functions