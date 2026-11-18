#pragma once
#include <userver/formats/json.hpp>
#include <exception>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <variant>

#include <userver/engine/task/task_with_result.hpp>
#include <userver/utils/async.hpp>
#include <eventprocessor/internal/types/event.hpp>
#include <eventprocessor/internal/types/publication_outcome.hpp>

#include <servicelib/runtime/common.hpp>
#include <servicelib/runtime/config/endpoint_types.hpp>
#include <servicelib/runtime/environment/environment.hpp>
#include <servicelib/datasink/nats/userver.hpp>

namespace nats_events::event_processor::functions {
struct PublishCoreEventSink final {
  using State = std::monostate;
  // Called on the application task processor, never a native NATS callback thread.
  void onError(servicelib::MessageContext context, auto& stream, std::exception_ptr error) const {
    stream.collectError(std::move(context), std::move(error));
  }
  servicelib::BeginResult<State> beginRequest(servicelib::MessageContext context, auto&) const {
    return {std::move(context), {}};
  }

  std::string getStreamId(servicelib::MessageContext context, const nats_events::event_processor::types::Event&) const { return std::string{context.streamId()}; }
  // Set value/headers and call send with a delivery-to-result mapping, or use
  // sendSync then out. Do not conflate ordinary results and typed errors.
  // send reports local admission only. sendSync also flushes; neither confirms processing.
  void consumeMessage(servicelib::MessageContext,auto&,State&,const types::Event& value,
      servicelib::datasink::nats::SinkMessage<types::PublicationOutcome>& message) const {
    userver::formats::json::ValueBuilder output;
    output["ID"]=value.ID; output["Value"]=value.Value;
    message.value=userver::formats::json::ToString(output.ExtractValue());
    message.send([id=value.ID](const servicelib::nats::DeliveryResult& result) {
      return types::PublicationOutcome{id,result.accepted && !result.error,result.error ? "publish failed" : ""};
    });
  }

  // endRequest follows handler return. Sink delivery callbacks may outlive it;
  // keep their captured state alive. Source completion is never implicit ACK.
  void endRequest(servicelib::MessageContext, auto&, std::exception_ptr, State&) const noexcept {}
};
inline userver::engine::TaskWithResult<std::unique_ptr<PublishCoreEventSink>> MakePublishCoreEventSink(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::NATSEndpointConfig& config) {
  return userver::utils::Async(
      "make-publish_core_event_sink", [context = std::move(context), &environment, &config]() mutable {
        (void)context;
        (void)environment;
        (void)config;
        return std::make_unique<PublishCoreEventSink>();
      });
}
}  // namespace nats_events::event_processor::functions