#pragma once
#include <exception>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <variant>

#include <userver/engine/task/task_with_result.hpp>
#include <userver/utils/async.hpp>
#include <storageworker/internal/types/storage_request.hpp>
#include <storageworker/internal/types/storage_result.hpp>

#include <servicelib/runtime/common.hpp>
#include <servicelib/runtime/config/endpoint_types.hpp>
#include <servicelib/runtime/environment/environment.hpp>


#include <servicelib/dataquery/endpoint.hpp>
#include <servicelib/dataquery/s3/operations.hpp>

namespace storage_query::storage_worker::functions {

class PutObjectQuery {
 public:
  using State = std::string;
  using Request = servicelib::dataquery::s3::PutObjectRequest;

  servicelib::dataquery::BeginRequest<State> beginRequest(
      servicelib::MessageContext context, auto&) const {
    return {std::move(context), {}, {}};
  }

  // Build the native operation request. The adapter owns the response lifetime
  // and performs no replay. GetObject returns a complete buffered object.
  Request buildRequest(servicelib::MessageContext, State& state, const storage_query::storage_worker::types::StorageRequest& value) const {
    state = value.requestId;
    Request request; request.key = value.key; request.body = value.value;
    return request;
  }

  void handleResult(
      servicelib::MessageContext context, State& state, const std::string& result,
      servicelib::dataquery::Collector<storage_query::storage_worker::types::StorageResult>& out) const {
    out.out(context, storage_query::storage_worker::types::StorageResult{state, "command", result});
  }

  // Map errors to the application's error type. Emit completion through out
  // only if the application needs it; there is no separate completion port.
  void endRequest(
      servicelib::MessageContext context, auto&, State* state, std::exception_ptr error,
      servicelib::dataquery::Collector<storage_query::storage_worker::types::StorageResult>& out,
      servicelib::dataquery::Collector<std::exception_ptr>& errors) const {
    if (error) { errors.out(context, error); return; }
    if (!state) throw std::logic_error("Successful Query has no request state");
    out.out(context, storage_query::storage_worker::types::StorageResult{*state, "completed", {}});
  }
};

inline userver::engine::TaskWithResult<std::unique_ptr<PutObjectQuery>> MakePutObjectQuery(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::QueryEndpointConfig& config) {
  return userver::utils::Async(
      "make-put_object_query", [context = std::move(context), &environment, &config]() mutable {
        (void)context;
        (void)environment;
        (void)config;
        return std::make_unique<PutObjectQuery>();
      });
}
}  // namespace storage_query::storage_worker::functions
