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

#include <servicelib/datasource/redisstreams/client.hpp>
#include <servicelib/runtime/common.hpp>
#include <servicelib/runtime/config/endpoint_types.hpp>
#include <servicelib/runtime/environment/environment.hpp>

namespace redis_streams_events::event_processor::functions {
struct ReceiveEventSource final {
  using State = std::monostate;
  int concurrency(auto &) const noexcept { return 1; }

  // Resumes on the application executor, never a native RedisStreams callback
  // thread.
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
  // with native entry ID. Retain the copyable native message for callbacks.
  // Processing must be idempotent.
  boost::asio::awaitable<void>
  consumeMessage(servicelib::MessageContext context, auto &stream, State &,
                 const servicelib::redisstreams::Message &message,
                 auto result) const {
    types::Event event;
    bool hasID = false, hasValue = false;
    for (const auto &[key, value] : message.native().fields) {
      if (key == "ID") {
        if (hasID)
          throw std::runtime_error("duplicate event ID");
        event.ID = value;
        hasID = true;
      } else if (key == "Value") {
        if (hasValue)
          throw std::runtime_error("duplicate event Value");
        event.Value = value;
        hasValue = true;
      }
    }
    if (!hasID || !hasValue)
      throw std::runtime_error("missing event fields");
    result.setResultCallback(
        event.ID,
        [message, result, id = event.ID](
            servicelib::MessageContext callbackContext, auto &, State &,
            const types::PublicationOutcome &outcome) mutable
            -> boost::asio::awaitable<bool> {
          if (outcome.EventID == id && outcome.Accepted &&
              !outcome.EntryID.empty())
            co_await message.ack(callbackContext);
          // Failed publications remain unacknowledged; no implicit retry here.
          std::osyncstream(std::cout)
              << boost::json::serialize(
                     boost::json::object{{"EventID", outcome.EventID},
                                         {"EntryID", outcome.EntryID},
                                         {"Accepted", outcome.Accepted},
                                         {"Reason", outcome.Reason}})
              << std::endl;
          result.done();
          co_return true;
        });
    co_await stream.collect(std::move(context), std::move(event));
  }
  boost::asio::awaitable<std::string> getMessageId(
      servicelib::MessageContext, auto &, State &,
      const redis_streams_events::event_processor::types::PublicationOutcome
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
MakeReceiveEventSource(
    servicelib::Context context, servicelib::IServiceEnvironment &environment,
    const servicelib::config::RedisStreamsEndpointConfig &config) {
  (void)context;
  (void)environment;
  (void)config;
  co_return std::make_unique<ReceiveEventSource>();
}
} // namespace redis_streams_events::event_processor::functions