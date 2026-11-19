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

class ExecuteQuery {
 public:
  using State = std::string;
  using Transaction = userver::storages::postgres::Transaction;
  using NativeResult = userver::storages::postgres::ResultSet;

  servicelib::dataquery::BeginRequest<State> beginRequest(
      servicelib::MessageContext context, auto&) const {
    return {std::move(context), {}, {}};
  }

  // Return a callable using Transaction::Execute with typed parameters.
  // The adapter owns commit/rollback and never retries this operation.
  std::function<NativeResult(Transaction&)> buildQuery(
      servicelib::MessageContext, State& state, const storage_query::storage_worker::types::StorageRequest& value) const {
    state = value.requestId;
    return [value](Transaction& transaction) { return transaction.Execute("INSERT INTO query_example_items (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", value.key, userver::storages::postgres::Bytea(value.value)); };
  }

  void handleResult(
      servicelib::MessageContext context, State& state, const userver::storages::postgres::ResultSet& result,
      servicelib::dataquery::Collector<storage_query::storage_worker::types::StorageResult>& out) const {
    out.out(context, storage_query::storage_worker::types::StorageResult{state, "command", std::to_string(result.RowsAffected())});
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

inline userver::engine::TaskWithResult<std::unique_ptr<ExecuteQuery>> MakeExecuteQuery(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::QueryEndpointConfig& config) {
  return userver::utils::Async(
      "make-execute_query", [context = std::move(context), &environment, &config]() mutable {
        (void)context;
        (void)environment;
        (void)config;
        return std::make_unique<ExecuteQuery>();
      });
}
}  // namespace storage_query::storage_worker::functions
