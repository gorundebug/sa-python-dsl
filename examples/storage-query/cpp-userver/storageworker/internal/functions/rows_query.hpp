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

#include <functional>
#include <userver/storages/postgres/io/bytea.hpp>
#include <servicelib/dataquery/endpoint.hpp>
#include <userver/storages/postgres/transaction.hpp>
#include <userver/storages/postgres/portal.hpp>

namespace storage_query::storage_worker::functions {

class RowsQuery {
 public:
  using State = std::string;
  using Transaction = userver::storages::postgres::Transaction;
  using NativeResult = userver::storages::postgres::Portal;

  servicelib::dataquery::BeginRequest<State> beginRequest(
      servicelib::MessageContext context, auto&) const {
    return {std::move(context), {}, {}};
  }

  // Return a callable using Transaction::MakePortal with typed parameters.
  // The adapter owns commit/rollback and never retries this operation.
  std::function<NativeResult(Transaction&)> buildQuery(
      servicelib::MessageContext, State& state, const storage_query::storage_worker::types::StorageRequest& value) const {
    state = value.requestId;
    return [value](Transaction& transaction) { return transaction.MakePortal("SELECT value FROM query_example_items WHERE key = $1", value.key); };
  }

  void handleRow(
      servicelib::MessageContext context, State& state, const userver::storages::postgres::Row& result,
      servicelib::dataquery::Collector<storage_query::storage_worker::types::StorageResult>& out) const {
    out.out(context, storage_query::storage_worker::types::StorageResult{state, "record", result[0].As<userver::storages::postgres::ByteaWrapper<std::string>>().bytes});
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

inline userver::engine::TaskWithResult<std::unique_ptr<RowsQuery>> MakeRowsQuery(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::QueryEndpointConfig& config) {
  return userver::utils::Async(
      "make-rows_query", [context = std::move(context), &environment, &config]() mutable {
        (void)context;
        (void)environment;
        (void)config;
        return std::make_unique<RowsQuery>();
      });
}
}  // namespace storage_query::storage_worker::functions
