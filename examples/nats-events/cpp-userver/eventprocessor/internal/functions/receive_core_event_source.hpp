#pragma once
#include <iostream>
#include <syncstream>
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
#include <servicelib/datasource/nats/userver.hpp>

namespace nats_events::event_processor::functions {
struct ReceiveCoreEventSource final {
  using State = std::monostate;
  // Called on the application task processor, never a native NATS callback thread.
  void onError(servicelib::MessageContext context, auto& stream, std::exception_ptr error) const {
    stream.collectError(std::move(context), std::move(error));
  }
  servicelib::BeginResult<State> beginRequest(servicelib::MessageContext context, auto&) const {
    return {std::move(context), {}};
  }

  // Register result callbacks before collect; preserve the context and correlation ID.
  // Done finalizes graph processing. It never acknowledges a broker message.
  // Core has no ACK or replay. Calling ack on a Core message is an error.
  void consumeMessage(servicelib::MessageContext context, auto& stream, State&,
      const servicelib::datasource::nats::ConsumerMessage& message, auto result) const {
    const auto input = userver::formats::json::FromString(std::string{message.data()});
    types::Event value{input["ID"].As<std::string>(),input["Value"].As<std::string>()};
    result.setResultCallback(value.ID, [message,result](servicelib::MessageContext,auto&,State&,const types::PublicationOutcome& outcome) mutable {
      if(message.jetStream()) { if(outcome.Accepted) message.doubleAck(); else message.nak(); }
      userver::formats::json::ValueBuilder log;
      log["EventID"]=outcome.EventID; log["Accepted"]=outcome.Accepted; log["Reason"]=outcome.Reason;
      std::osyncstream(std::cout) << userver::formats::json::ToString(log.ExtractValue()) << std::endl;
      result.done(); return true;
    });
    stream.collect(std::move(context),std::move(value));
  }
  std::string getMessageId(servicelib::MessageContext,auto&,State&,const types::PublicationOutcome& outcome) const {return outcome.EventID;}

  // endRequest follows handler return. Sink delivery callbacks may outlive it;
  // keep their captured state alive. Source completion is never implicit ACK.
  void endRequest(servicelib::MessageContext, auto&, std::exception_ptr, State&) const noexcept {}
};
inline userver::engine::TaskWithResult<std::unique_ptr<ReceiveCoreEventSource>> MakeReceiveCoreEventSource(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::NATSEndpointConfig& config) {
  return userver::utils::Async(
      "make-receive_core_event_source", [context = std::move(context), &environment, &config]() mutable {
        (void)context;
        (void)environment;
        (void)config;
        return std::make_unique<ReceiveCoreEventSource>();
      });
}
}  // namespace nats_events::event_processor::functions