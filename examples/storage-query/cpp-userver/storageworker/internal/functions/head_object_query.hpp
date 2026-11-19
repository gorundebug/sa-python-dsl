#pragma once
#include <exception>
#include <userver/formats/json/value_builder.hpp>
#include <userver/formats/json/serialize.hpp>
#include <userver/http/common_headers.hpp>
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

class HeadObjectQuery {
 public:
  using State = std::string;
  using Request = servicelib::dataquery::s3::HeadObjectRequest;

  servicelib::dataquery::BeginRequest<State> beginRequest(
      servicelib::MessageContext context, auto&) const {
    return {std::move(context), {}, {}};
  }

  // Build the native operation request. The adapter owns the response lifetime
  // and performs no replay. GetObject returns a complete buffered object.
  Request buildRequest(servicelib::MessageContext, State& state, const storage_query::storage_worker::types::StorageRequest& value) const {
    state = value.requestId;
    Request request; request.key = value.key;
    return request;
  }

  void handleResult(
      servicelib::MessageContext context, State& state, const userver::clients::http::Response& result,
      servicelib::dataquery::Collector<storage_query::storage_worker::types::StorageResult>& out) const {
    const auto etag = result.headers().find(userver::http::headers::kETag);
    userver::formats::json::ValueBuilder metadata;
    metadata["size"] = std::stoll(result.headers().at(userver::http::headers::kContentLength));
    metadata["etag"] = etag == result.headers().end() ? std::string{} : etag->second;
    out.out(context, storage_query::storage_worker::types::StorageResult{state, "object", userver::formats::json::ToString(metadata.ExtractValue())});
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

inline userver::engine::TaskWithResult<std::unique_ptr<HeadObjectQuery>> MakeHeadObjectQuery(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::QueryEndpointConfig& config) {
  return userver::utils::Async(
      "make-head_object_query", [context = std::move(context), &environment, &config]() mutable {
        (void)context;
        (void)environment;
        (void)config;
        return std::make_unique<HeadObjectQuery>();
      });
}
}  // namespace storage_query::storage_worker::functions
