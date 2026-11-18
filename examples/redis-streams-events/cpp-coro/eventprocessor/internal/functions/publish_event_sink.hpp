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

#include <servicelib/datasink/redisstreams/client.hpp>
#include <servicelib/runtime/common.hpp>
#include <servicelib/runtime/config/endpoint_types.hpp>
#include <servicelib/runtime/environment/environment.hpp>

namespace redis_streams_events::event_processor::functions {
struct PublishEventSink final {
  using State = std::monostate;

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

  boost::asio::awaitable<std::string> getStreamId(
      servicelib::MessageContext context,
      const redis_streams_events::event_processor::types::Event &) const {
    co_return std::string{context.streamId()};
  }
  // Set native message fields and admit an async delivery-to-result mapping, or
  // use sendSync then out. Do not conflate ordinary results and typed errors.
  // Accepted carries the native broker entry ID, not a downstream processing
  // ACK.
  boost::asio::awaitable<void> consumeMessage(
      servicelib::MessageContext, auto &, State &, const types::Event &event,
      servicelib::datasink::redisstreams::SinkMessage<types::PublicationOutcome>
          &message) const {
    message.message.fields = {{"ID", event.ID}, {"Value", event.Value}};
    message.send(
        [id = event.ID](
            const servicelib::datasink::redisstreams::DeliveryResult &delivery)
            -> boost::asio::awaitable<types::PublicationOutcome> {
          const bool accepted =
              delivery.outcome == servicelib::redisstreams::Outcome::Accepted;
          co_return types::PublicationOutcome{
              id, accepted ? delivery.id : "", accepted,
              delivery.error ? "publish failed" : ""};
        });
    co_return;
  }

  // endRequest follows handler return. Sink delivery callbacks may outlive it;
  // keep their captured state alive. Source completion is never implicit ACK.
  boost::asio::awaitable<void> endRequest(servicelib::MessageContext, auto &,
                                          std::exception_ptr, State &) const {
    co_return;
  }
};
inline boost::asio::awaitable<std::unique_ptr<PublishEventSink>>
MakePublishEventSink(
    servicelib::Context context, servicelib::IServiceEnvironment &environment,
    const servicelib::config::RedisStreamsEndpointConfig &config) {
  (void)context;
  (void)environment;
  (void)config;
  co_return std::make_unique<PublishEventSink>();
}
} // namespace redis_streams_events::event_processor::functions