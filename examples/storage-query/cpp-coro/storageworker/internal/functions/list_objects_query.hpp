#pragma once
#include <exception>
#include <boost/json.hpp>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <variant>

#include <boost/asio/awaitable.hpp>
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
  using Request = Aws::S3::Model::ListObjectsV2Request;

  boost::asio::awaitable<servicelib::dataquery::BeginRequest<State>> beginRequest(
      servicelib::MessageContext context, auto&) const {
    co_return servicelib::dataquery::BeginRequest<State>{std::move(context), {}, {}};
  }

  // Build the native operation request. The adapter owns the response lifetime
  // and performs no replay. GetObject returns a complete buffered object.
  boost::asio::awaitable<Request> buildRequest(servicelib::MessageContext, State& state, const storage_query::storage_worker::types::StorageRequest& value) const {
    state = value.requestId;
    Request request;
    request.SetBucket("query-example");
    request.SetPrefix(value.key.c_str());
    co_return request;
  }

  boost::asio::awaitable<void> handlePage(
      servicelib::MessageContext context, State& state, const Aws::S3::Model::ListObjectsV2Result& result,
      servicelib::dataquery::Collector<storage_query::storage_worker::types::StorageResult>& out) const {
    boost::json::array entries;
    for (const auto& item : result.GetContents()) {
      entries.push_back(boost::json::object{{"key", item.GetKey().c_str()}, {"size", item.GetSize()}});
    }
    co_await out.out(context, storage_query::storage_worker::types::StorageResult{state, "page", boost::json::serialize(entries)});
    co_return;
  }

  // Map errors to the application's error type. Emit completion through out
  // only if the application needs it; there is no separate completion port.
  boost::asio::awaitable<void> endRequest(
      servicelib::MessageContext context, auto&, State* state, std::exception_ptr error,
      servicelib::dataquery::Collector<storage_query::storage_worker::types::StorageResult>& out,
      servicelib::dataquery::Collector<std::exception_ptr>& errors) const {
    if (error) { co_await errors.out(context, error); co_return; }
    if (!state) throw std::logic_error("Successful Query has no request state");
    co_await out.out(context, storage_query::storage_worker::types::StorageResult{*state, "completed", {}});
    co_return;
  }
};

inline boost::asio::awaitable<std::unique_ptr<ListObjectsQuery>> MakeListObjectsQuery(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::QueryEndpointConfig& config) {
  (void)context;
  (void)environment;
  (void)config;
  co_return std::make_unique<ListObjectsQuery>();
}
}  // namespace storage_query::storage_worker::functions
