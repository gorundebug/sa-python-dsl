#pragma once
#include <exception>
#include <userver/formats/json/value_builder.hpp>
#include <userver/formats/json/serialize.hpp>
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

class ListObjectsQuery {
 public:
  using State = std::string;
  using Request = servicelib::dataquery::s3::ListObjectsRequest;

  servicelib::dataquery::BeginRequest<State> beginRequest(
      servicelib::MessageContext context, auto&) const {
    return {std::move(context), {}, {}};
  }

  // Build the native operation request. The adapter owns the response lifetime
  // and performs no replay. GetObject returns a complete buffered object.
  Request buildRequest(servicelib::MessageContext, State& state, const storage_query::storage_worker::types::StorageRequest& value) const {
    state = value.requestId;
    Request request; request.prefix = value.key;
    return request;
  }

  void handlePage(
      servicelib::MessageContext context, State& state, const std::string& result,
      servicelib::dataquery::Collector<storage_query::storage_worker::types::StorageResult>& out) const {
    pugi::xml_document document;
    if (!document.load_buffer(result.data(), result.size())) throw std::runtime_error("Invalid listing XML");
    userver::formats::json::ValueBuilder entries(userver::formats::json::Type::kArray);
    for (auto item : document.child("ListBucketResult").children("Contents")) {
      userver::formats::json::ValueBuilder entry;
      entry["key"] = std::string(item.child("Key").child_value());
      entry["size"] = item.child("Size").text().as_llong();
      entries.PushBack(entry.ExtractValue());
    }
    out.out(context, storage_query::storage_worker::types::StorageResult{state, "page", userver::formats::json::ToString(entries.ExtractValue())});
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

inline userver::engine::TaskWithResult<std::unique_ptr<ListObjectsQuery>> MakeListObjectsQuery(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::QueryEndpointConfig& config) {
  return userver::utils::Async(
      "make-list_objects_query", [context = std::move(context), &environment, &config]() mutable {
        (void)context;
        (void)environment;
        (void)config;
        return std::make_unique<ListObjectsQuery>();
      });
}
}  // namespace storage_query::storage_worker::functions
