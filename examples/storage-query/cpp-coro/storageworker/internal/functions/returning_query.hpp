#pragma once
#include <exception>
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

#include <libpq-fe.h>
#include <servicelib/dataquery/endpoint.hpp>
#include <servicelib/dataquery/postgres/connection.hpp>

namespace storage_query::storage_worker::functions {

class ReturningQuery {
 public:
  using State = std::string;
  boost::asio::awaitable<servicelib::dataquery::BeginRequest<State>> beginRequest(
      servicelib::MessageContext context, auto&) const {
    co_return servicelib::dataquery::BeginRequest<State>{std::move(context), {}, {}};
  }

  // Construct parameterized SQL in code; values are bound separately.
  // The adapter owns connection lifetime and never retries this operation.
  boost::asio::awaitable<servicelib::dataquery::postgres::Statement> buildQuery(
      servicelib::MessageContext, State& state, const storage_query::storage_worker::types::StorageRequest& value) const {
    state = value.requestId;
    servicelib::dataquery::postgres::Statement statement;
    statement.sql = "INSERT INTO query_example_items (key, value) VALUES ($1, $2) RETURNING value";
    statement.parameters.push_back({value.key, 25, 0}); // PostgreSQL text OID.
    statement.parameters.push_back({value.value, 17, 1}); // Binary bytea parameter.
    statement.resultFormat = 1; // bytea result: binary bytes, no text unescaping.
    co_return statement;
  }

  boost::asio::awaitable<void> handleRow(
      servicelib::MessageContext context, State& state, const PGresult& result,
      servicelib::dataquery::Collector<storage_query::storage_worker::types::StorageResult>& out) const {
    if (PQnfields(&result) != 1 || PQntuples(&result) != 1 || PQgetisnull(&result, 0, 0)) throw std::runtime_error("Expected a non-null bytea row");
    co_await out.out(context, storage_query::storage_worker::types::StorageResult{state, "record", std::string(PQgetvalue(&result, 0, 0), static_cast<std::size_t>(PQgetlength(&result, 0, 0)))});
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

inline boost::asio::awaitable<std::unique_ptr<ReturningQuery>> MakeReturningQuery(
    servicelib::Context context, servicelib::IServiceEnvironment& environment,
    const servicelib::config::QueryEndpointConfig& config) {
  (void)context;
  (void)environment;
  (void)config;
  co_return std::make_unique<ReturningQuery>();
}
}  // namespace storage_query::storage_worker::functions
