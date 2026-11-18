#pragma once
#include <userver/engine/task/task_with_result.hpp>
#include <userver/utils/async.hpp>
#include <userver/formats/json.hpp>
#include <exception>
#include <memory>
#include <openssl/evp.h>
#include <stdexcept>
#include <string>
#include <utility>
#include <variant>

#include <eventprocessor/internal/types/event.hpp>
#include <eventprocessor/internal/types/publication_outcome.hpp>

#include <servicelib/datasink/pulsar/client.hpp>
#include <servicelib/runtime/common.hpp>
#include <servicelib/runtime/config/endpoint_types.hpp>
#include <servicelib/runtime/environment/environment.hpp>

namespace pulsar_events::event_processor::functions {
struct PublishEventSink final {
  using State = std::monostate;

  // Resumes on the application executor, never a native Pulsar callback thread.
  void onError(servicelib::MessageContext context,
                                       auto &stream,
                                       std::exception_ptr error) const {
    stream.collectError(std::move(context), std::move(error));
    return;
  }
  servicelib::BeginResult<State>
  beginRequest(servicelib::MessageContext context, auto &) const {
    return servicelib::BeginResult<State>{std::move(context), {}};
  }

  std::string
  getStreamId(servicelib::MessageContext context,
              const pulsar_events::event_processor::types::Event &) const {
    return std::string{context.streamId()};
  }
  // Set native message fields and admit an async delivery-to-result mapping, or
  // use sendSync then out. Do not conflate ordinary results and typed errors.
  // Accepted carries the native broker MessageId, not a downstream processing
  // ACK.
  void consumeMessage(
      servicelib::MessageContext, auto &, State &, const types::Event &event,
      servicelib::datasink::pulsar::SinkMessage<types::PublicationOutcome>
          &message) const {
    message.message.key = event.ID;
    message.message.properties["example"] = "pulsar-events";
    userver::formats::json::ValueBuilder output;
    output["ID"] = event.ID;
    output["Value"] = event.Value;
    message.message.data = userver::formats::json::ToString(output.ExtractValue());
    message.send(
        [id = event.ID](
            const servicelib::datasink::pulsar::DeliveryResult &delivery)
            -> types::PublicationOutcome {
          const bool accepted =
              delivery.outcome == servicelib::pulsar::Outcome::Accepted;
          std::string messageID;
          if (accepted) {
            std::string bytes;
            delivery.id.serialize(bytes);
            messageID.resize(4 * ((bytes.size() + 2) / 3));
            EVP_EncodeBlock(
                reinterpret_cast<unsigned char *>(messageID.data()),
                reinterpret_cast<const unsigned char *>(bytes.data()),
                static_cast<int>(bytes.size()));
          }
          return types::PublicationOutcome{
              id, messageID, accepted, delivery.error ? "publish failed" : ""};
        });
    return;
  }

  // endRequest follows handler return. Sink delivery callbacks may outlive it;
  // keep their captured state alive. Source completion is never implicit ACK.
  void endRequest(servicelib::MessageContext, auto &,
                                          std::exception_ptr, State &) const {
    return;
  }
};
inline userver::engine::TaskWithResult<std::unique_ptr<PublishEventSink>>
MakePublishEventSink(servicelib::Context context,
  servicelib::IServiceEnvironment& environment,
  const servicelib::config::PulsarEndpointConfig& config) {
  return userver::utils::Async("make-PublishEventSink",
      [context = std::move(context), &environment, &config] {
        (void)context; (void)environment; (void)config;
        return std::make_unique<PublishEventSink>();
      });
}
} // namespace pulsar_events::event_processor::functions