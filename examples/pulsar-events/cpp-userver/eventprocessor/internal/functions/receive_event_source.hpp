#pragma once
#include <userver/engine/task/task_with_result.hpp>
#include <userver/utils/async.hpp>
#include <userver/formats/json.hpp>
#include <exception>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <syncstream>
#include <utility>
#include <variant>

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

  // Register result callbacks before collect; preserve the context and
  // correlation ID. Done finalizes graph processing. It never acknowledges a
  // broker message. Individually ACK only a correlated accepted publication
  // with native MessageId. Retain the copyable native message for callbacks.
  // Processing must be idempotent.
  void
  consumeMessage(servicelib::MessageContext context, auto &stream, State &,
                 const servicelib::pulsar::Message &message,
                 auto result) const {
    const auto object =
        userver::formats::json::FromString(message.native().getDataAsString());
    types::Event event{object["ID"].As<std::string>(),
                       object["Value"].As<std::string>()};
    result.setResultCallback(
        event.ID,
        [message, result](servicelib::MessageContext callbackContext, auto &,
                          State &,
                          const types::PublicationOutcome &outcome) mutable
            -> bool {
          if (outcome.Accepted && !outcome.MessageID.empty())
            message.ack(callbackContext);
          // Failed publications remain unacknowledged; no implicit retry here.
          userver::formats::json::ValueBuilder log;
          log["EventID"] = outcome.EventID;
          log["MessageID"] = outcome.MessageID;
          log["Accepted"] = outcome.Accepted;
          log["Reason"] = outcome.Reason;
          std::osyncstream(std::cout)
              << userver::formats::json::ToString(log.ExtractValue()) << std::endl;
          result.done();
          return true;
        });
    stream.collect(std::move(context), std::move(event));
  }
  std::string
  getMessageId(servicelib::MessageContext, auto &, State &,
               const pulsar_events::event_processor::types::PublicationOutcome
                   &value) const {
    return value.EventID;
  }

  // endRequest follows handler return. Sink delivery callbacks may outlive it;
  // keep their captured state alive. Source completion is never implicit ACK.
  void endRequest(servicelib::MessageContext, auto &,
                                          std::exception_ptr, State &) const {
    return;
  }
};
inline userver::engine::TaskWithResult<std::unique_ptr<ReceiveEventSource>>
MakeReceiveEventSource(servicelib::Context context,
  servicelib::IServiceEnvironment& environment,
  const servicelib::config::PulsarEndpointConfig& config) {
  return userver::utils::Async("make-ReceiveEventSource",
      [context = std::move(context), &environment, &config] {
        (void)context; (void)environment; (void)config;
        return std::make_unique<ReceiveEventSource>();
      });
}
} // namespace pulsar_events::event_processor::functions