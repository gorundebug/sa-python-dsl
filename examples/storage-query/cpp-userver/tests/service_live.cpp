// Test-only replacement for the generated service extension, never production code.
#include "storageworker/internal/app/service.hpp"
#include <algorithm>
#include <atomic>
#include <userver/engine/sleep.hpp>
#include <userver/components/run.hpp>
#include <userver/storages/postgres/statistics.hpp>
#include <userver/utils/async.hpp>
#include <servicelib/dataquery/postgres/operations.hpp>
#include <servicelib/dataquery/s3/operations.hpp>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <limits>
#include <optional>
#include <userver/storages/postgres/io/bytea.hpp>
#include <vector>
#include <userver/formats/json/serialize.hpp>
#include <userver/formats/json/value.hpp>

namespace storage_query::storage_worker::app {
namespace {
using Request = types::StorageRequest;
using Result = types::StorageResult;
// Test-only handle obtained from the normal generated infrastructure maker.
userver::storages::postgres::ClusterPtr nativePostgres;
std::shared_ptr<servicelib::dataquery::s3::Connector> nativeS3;
void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
struct NativeRowsProbe {
  std::string sql;
  int failAfter = 0;
  bool typed = false;
  auto buildQuery(servicelib::MessageContext, int&, const std::string& key) {
    return [sql = sql, key](userver::storages::postgres::Transaction& transaction) {
      return transaction.MakePortal(sql, key);
    };
  }
  void handleRow(servicelib::MessageContext context, int& count,
                 const userver::storages::postgres::Row& row,
                 servicelib::dataquery::Collector<std::string>& out) {
    if (failAfter && count == failAfter) throw std::runtime_error("intentional mapper failure");
    if (typed) {
      require(!row[1].As<std::optional<std::string>>(), "NULL lost");
      require(row[2].As<std::int64_t>() == std::numeric_limits<std::int64_t>::max(), "int64 lost precision");
      // Explicit SQL text mapping preserves arbitrary numeric precision and
      // timestamp microseconds without imposing a custom SDK codec.
      require(row[3].As<std::string>() == "12345678901234567890.123456789012345678", "numeric lost precision");
      require(row[4].As<std::string>() == "2026-11-19 09:34:56.123456", "timestamp/timezone mismatch");
      require(row[5].As<std::string>() == "123e4567-e89b-12d3-a456-426614174000", "UUID mismatch");
      require(row[6].As<userver::storages::postgres::ByteaWrapper<std::string>>().bytes == std::string("a\0\xff", 3), "bytea mismatch");
      const auto json = userver::formats::json::FromString(row[7].As<std::string>());
      require(json["value"][0].As<int>() == 1 && json["value"][1].IsNull() &&
          json["value"][2].As<std::string>() == "quoted", "JSON mismatch");
    }
    ++count;
    out.out(context, row[0].As<std::string>());
  }
};
void checkNativeRows(servicelib::Context parent) {
  using namespace std::chrono_literals;
  const auto cluster = std::exchange(nativePostgres, {});
  servicelib::dataquery::postgres::Rows operation(cluster, 7);
  {
    NativeRowsProbe handler{"SELECT i::text FROM generate_series(1,10000) i WHERE $1::text = 'large'"};
    int count = 0;
    std::atomic<int> delivered{0};
    servicelib::dataquery::Collector<std::string> out(
        [&](servicelib::MessageContext, servicelib::Payload<std::string> value) {
          const int index = ++delivered;
          require(std::stoi(value.get()) == index, "large selection reordered rows");
          if (index == 1) {
            auto observer = userver::utils::Async("query-slow-mapper-observer", [&] {
              userver::engine::SleepFor(5ms);
              require(delivered.load() == 1, "Query emitted while collector was blocked");
            });
            userver::engine::SleepFor(20ms);
            observer.Get();
          }
        });
    servicelib::dataquery::detail::runRequestTask(servicelib::MessageContext(parent), [&] {
      operation.execute(servicelib::MessageContext(parent), count, std::string("large"), handler, out);
    }, 10s);
    require(count == 10000 && delivered == 10000, "large selection lost rows");
    // Reuse the maker-owned one-connection pool after portal cleanup.
    auto transaction = cluster->Begin(userver::storages::postgres::Transaction::RW);
    const auto reused = transaction.Execute("SELECT 1");
    require(reused[0][0].As<int>() == 1, "pool not reusable after large selection");
    transaction.Commit();
    std::cout << "QUERY_NATIVE_LARGE_ROWS_PASSED" << std::endl;
  }

  {
    NativeRowsProbe handler{
      "SELECT $1::text, NULL::text, 9223372036854775807::bigint, "
      "12345678901234567890.123456789012345678::numeric::text, "
      "('2026-11-19 12:34:56.123456+03'::timestamptz AT TIME ZONE 'UTC')::text, "
      "'123e4567-e89b-12d3-a456-426614174000'::uuid::text, decode('6100ff','hex'), "
      "jsonb_build_object('value',jsonb_build_array(1,NULL,'quoted'))::text", 0, true};
    int count = 0;
    std::vector<std::string> values;
    servicelib::dataquery::Collector<std::string> out(
        [&](servicelib::MessageContext, servicelib::Payload<std::string> value) { values.push_back(value.get()); });
    servicelib::dataquery::detail::runRequestTask(servicelib::MessageContext(parent), [&] {
      operation.execute(servicelib::MessageContext(parent), count, std::string("bound-'key"), handler, out);
    }, 2s);
    require(count == 1 && values == std::vector<std::string>{"bound-'key"}, "typed bound row mismatch");
    std::cout << "QUERY_NATIVE_TYPES_PASSED" << std::endl;
  }
  const std::string insert = "INSERT INTO query_example_items (key,value) "
      "SELECT $1 || i::text, decode('00ff','hex') FROM generate_series(1,128) i RETURNING key";
  auto countStored = [&](const std::string& prefix) {
    auto transaction = cluster->Begin(userver::storages::postgres::Transaction::RW);
    auto result = transaction.Execute("SELECT count(*) FROM query_example_items WHERE key LIKE $1", prefix + "%");
    const auto count = result.AsSingleRow<std::int64_t>();
    transaction.Commit();
    return count;
  };
  for (const bool failing : {false, true}) {
    NativeRowsProbe handler{insert, failing ? 3 : 0};
    int mapped = 0;
    std::vector<std::string> emitted;
    servicelib::dataquery::Collector<std::string> out(
        [&](servicelib::MessageContext, servicelib::Payload<std::string> value) {
          emitted.push_back(value.get());
        });
    const std::string prefix = failing ? "rollback-" : "returning-";
    bool failed = false;
    try {
      servicelib::dataquery::detail::runRequestTask(servicelib::MessageContext(parent), [&] {
        operation.execute(servicelib::MessageContext(parent), mapped, prefix, handler, out);
      }, 2s);
    } catch (const std::exception&) { failed = true; }
    require(failed == failing, "RETURNING mapper outcome mismatch");
    require(emitted.size() == (failing ? 3u : 128u), "RETURNING partial rows mismatch");
    require(std::all_of(emitted.begin(), emitted.end(), [&](const auto& key) {
      return key.starts_with(prefix);
    }), "RETURNING bound parameter mismatch");
    require(countStored(prefix) == (failing ? 0 : 128), "RETURNING commit/rollback mismatch");
  }
  NativeRowsProbe slow{"SELECT $1::text FROM pg_sleep(10)"};
  int mapped = 0;
  servicelib::dataquery::Collector<std::string> out(
      [](servicelib::MessageContext, servicelib::Payload<std::string>) {});
  bool cancelled = false;
  const auto start = std::chrono::steady_clock::now();
  try {
    servicelib::dataquery::detail::runRequestTask(servicelib::MessageContext(parent), [&] {
      operation.execute(servicelib::MessageContext(parent), mapped, std::string("slow"), slow, out);
    }, 50ms);
  } catch (...) { cancelled = true; }
  require(cancelled && mapped == 0, "native SQL deadline did not cancel operation");
  require(std::chrono::steady_clock::now() - start < 5s, "native SQL cancellation waited for full query");
  require(countStored("returning-") == 128, "single-connection pool unusable after cancellation");
  std::cout << "QUERY_NATIVE_RETURNING_ROLLBACK_DEADLINE_PASSED" << std::endl;
}
template <typename RequestType>
struct S3Probe {
  RequestType request;
  int mapped = 0;
  bool fail = false;
  std::vector<std::string> keys;
  std::size_t expectedSize = 0;
  RequestType buildRequest(servicelib::MessageContext, int&, const std::string&) { return request; }
  void handleResult(servicelib::MessageContext, int&, const auto& result,
                    servicelib::dataquery::Collector<std::string>&) {
    ++mapped;
    if constexpr (std::is_same_v<RequestType, servicelib::dataquery::s3::GetObjectRequest>)
      require(result.body.size() == expectedSize &&
              result.body.find_first_not_of('x') == std::string::npos, "GetObject body mismatch");
    else
      require(result.headers().at(userver::http::headers::kContentLength) == "0", "empty HeadObject size mismatch");
    if (fail) throw std::runtime_error("intentional body mapper failure");
  }
  void handlePage(servicelib::MessageContext, int&, const std::string& xml,
                  servicelib::dataquery::Collector<std::string>&) {
    ++mapped;
    pugi::xml_document page;
    require(page.load_buffer(xml.data(), xml.size()), "invalid list XML");
    for (auto item : page.child("ListBucketResult").children("Contents"))
      keys.emplace_back(item.child("Key").child_value());
    if (fail) throw std::runtime_error("intentional page mapper failure");
  }
};
struct EndpointTestEnvironment final : servicelib::IServiceEnvironment {
  servicelib::log::NoopLogger logger;
  std::shared_ptr<const servicelib::config::RuntimeConfig> getRuntimeConfigSnapshot() const override { return {}; }
  std::shared_ptr<const servicelib::config::ServiceConfig> getServiceConfigSnapshot() const override { return {}; }
  servicelib::log::Logger& getLogger() override { return logger; }
  servicelib::metrics::Metrics& getMetrics() override { return servicelib::metrics::NoopMetrics::instance(); }
  servicelib::tracing::Tracing* getTracing() override { return nullptr; }
};
struct EndpointTestStream final : servicelib::QueryEndpointStream<int, int, std::exception_ptr> {
  mutable EndpointTestEnvironment env;
  int results = 0;
  servicelib::IServiceEnvironment& environment() const override { return env; }
  int endpointId() const noexcept override { return 1; }
  std::size_t streamConfigId() const noexcept override { return 1; }
  void collectResult(servicelib::MessageContext, servicelib::Payload<int>) override { ++results; }
  void collectError(servicelib::MessageContext, servicelib::Payload<std::exception_ptr>) override {}
};
struct EndpointS3Handler {
  using State = int;
  int mode;
  int ends = 0;
  bool failed = false;
  bool mapperActive = false;
  servicelib::dataquery::BeginRequest<int> beginRequest(servicelib::MessageContext context, servicelib::QueryEndpointStream<int, int, std::exception_ptr>&) {
    return {context, 0, {}};
  }
  servicelib::dataquery::s3::GetObjectRequest buildRequest(servicelib::MessageContext, int&, const int&) {
    return {mode == 1 ? "missing-body" : "large-body"};
  }
  void handleResult(servicelib::MessageContext context, int& state,
      const servicelib::dataquery::s3::GetObjectResult& result, servicelib::dataquery::Collector<int>& out) {
    struct Scope { bool& active; Scope(bool& value) : active(value) { active = true; } ~Scope() { active = false; } } scope(mapperActive);
    require(result.body.size() == 16 * 1024 * 1024, "native endpoint body size mismatch");
    ++state; out.out(context, 1);
    if (mode == 2) throw std::runtime_error("intentional mapper failure");
    if (mode == 3) userver::engine::SleepFor(std::chrono::seconds(1));
  }
  void endRequest(servicelib::MessageContext, servicelib::QueryEndpointStream<int, int, std::exception_ptr>&, int* state,
      std::exception_ptr error, servicelib::dataquery::Collector<int>&, servicelib::dataquery::Collector<std::exception_ptr>&) {
    ++ends; failed = bool(error);
    require(!mapperActive && state && *state == (mode == 1 ? 0 : 1), "native finalization order/state mismatch");
  }
};
void checkNativeS3Endpoint(servicelib::Context context) {
  namespace s3 = servicelib::dataquery::s3;
  auto client = nativeS3->makeClient(servicelib::MessageContext(context), "query-example");
  client->PutObject("large-body", std::string(16 * 1024 * 1024, 'x'));
  for (const int mode : {0, 1, 2, 3, 0}) {
    EndpointTestStream stream;
    EndpointS3Handler handler{mode};
    servicelib::dataquery::Endpoint<int, int, std::exception_ptr, EndpointS3Handler&, s3::GetObject> endpoint(
        stream, handler, s3::GetObject(client), std::chrono::milliseconds(mode == 3 ? 500 : 5000));
    try { endpoint.consume(servicelib::MessageContext(context), servicelib::Payload<int>::make(1)); }
    catch (...) { require(mode == 3, "unexpected endpoint cancellation"); }
    require(handler.ends == 1 && handler.failed == (mode != 0), "native endpoint completion mismatch");
    require(stream.results == (mode == 1 ? 0 : 1), "partial results mismatch");
  }
  std::cout << "QUERY_NATIVE_S3_ENDPOINT_FINALIZATION_PASSED" << std::endl;
}
void checkNativeS3(servicelib::Context parent) {
  using namespace std::chrono_literals;
  namespace s3 = servicelib::dataquery::s3;
  auto connector = std::exchange(nativeS3, {});
  auto context = servicelib::MessageContext(parent);
  auto client = connector->makeClient(context, "query-example");
  // Fixture setup uses the same maker-created native client; operations below
  // exercise the Query adapters, including pagination and failure unwind.
  for (const auto* key : {"edges/one", "edges/two", "edges/three"})
    client->PutObject(key, "");
  int state = 0;
  servicelib::dataquery::Collector<std::string> out(
      [](servicelib::MessageContext, servicelib::Payload<std::string>) {});
  auto run = [&](auto& operation, auto& handler) {
    servicelib::dataquery::detail::runRequestTask(context, [&] {
      operation.execute(context, state, std::string{}, handler, out);
    }, 2s);
  };
  s3::GetObject get(client);
  s3::HeadObject head(connector, "query-example");
  for (const bool missing : {false, true}) {
    const std::string key = missing ? "edges/absent" : "edges/one";
    S3Probe<s3::GetObjectRequest> getHandler{{key}};
    S3Probe<s3::HeadObjectRequest> headHandler{{key}};
    bool getFailed = false, headFailed = false;
    try { run(get, getHandler); } catch (const std::exception&) { getFailed = true; }
    try { run(head, headHandler); } catch (const std::exception&) { headFailed = true; }
    require(getFailed == missing && headFailed == missing, "empty and missing S3 outcomes conflated");
    require(getHandler.mapped == (missing ? 0 : 1) && headHandler.mapped == (missing ? 0 : 1), "missing object reached mapper");
  }
  s3::ListObjects list(client);
  for (const bool fail : {false, true}) {
    S3Probe<s3::ListObjectsRequest> handler{{"edges/", "", 1}};
    handler.fail = fail;
    bool failed = false;
    try { run(list, handler); } catch (const std::exception&) { failed = true; }
    require(failed == fail, "listing mapper error lost");
    if (fail) require(handler.mapped == 1 && handler.keys.size() == 1, "partial listing replayed");
    else {
      require(handler.mapped >= 3 && handler.mapped <= 4, "pagination did not advance");
      require(handler.keys == std::vector<std::string>{"edges/one", "edges/three", "edges/two"}, "pagination lost or duplicated keys");
    }
  }
  S3Probe<s3::ListObjectsRequest> empty{{"edges/absent/", "", 1}};
  run(list, empty);
  require(empty.mapped == 1 && empty.keys.empty(), "empty listing failed");
  for (const auto* key : {"edges/one", "edges/two", "edges/three"}) client->DeleteObject(key);
  constexpr std::size_t largeSize = 16 * 1024 * 1024;
  client->PutObject("large-body", std::string(largeSize, 'x'));
  for (const bool fail : {false, true, false}) {
    S3Probe<s3::GetObjectRequest> handler{{"large-body"}};
    handler.expectedSize = largeSize;
    handler.fail = fail;
    bool failed = false;
    try { run(get, handler); } catch (const std::runtime_error&) { failed = true; }
    require(failed == fail && handler.mapped == 1, "large object mapping/recovery failed");
  }
  client->DeleteObject("large-body");
  std::cout << "QUERY_NATIVE_S3_LARGE_BODY_PASSED" << std::endl;
  std::cout << "QUERY_NATIVE_S3_EDGES_PASSED" << std::endl;
}
std::vector<Result> invoke(
    servicelib::Context parent, std::shared_ptr<servicelib::ISubStream<Request, Result>> entry,
    std::string key, std::string value, std::string id) {
  struct Output { std::mutex mutex; std::vector<Result> rows; };
  auto output = std::make_shared<Output>();
  auto collector = std::make_shared<servicelib::SubStreamCollectorFunc<Result>>(
      [output](servicelib::MessageContext, const Result& row) -> bool {
        std::lock_guard lock(output->mutex);
        output->rows.push_back(row);
        return row.kind == "completed";
      });
  auto context = servicelib::MessageContext(parent).withDeadline(
      std::chrono::steady_clock::now() + std::chrono::seconds(10));
  auto request = servicelib::Payload<Request>::make(Request{id, key, value});
  entry->consume(context, request, collector);
  std::lock_guard lock(output->mutex);
  require(std::count_if(output->rows.begin(), output->rows.end(),
      [](const auto& row) { return row.kind == "completed"; }) == 1, "expected one completion");
  require(std::all_of(output->rows.begin(), output->rows.end(),
      [&](const auto& row) { return row.requestId == id; }), "request correlation mismatch");
  return output->rows;
}
}
void Service::customMakersInit(servicelib::Context) {
  const auto standardS3 = makers_.objects_s3_connector;
  makers_.objects_s3_connector = [standardS3](servicelib::Context context,
      servicelib::IServiceEnvironment& environment,
      const servicelib::config::S3UserverDataConnectorConfig& config) {
    return userver::utils::Async("verify-query-s3-maker", [standardS3, context, &environment, config] {
      auto connector = standardS3(context, environment, config).Get();
      nativeS3 = connector;
      return connector;
    });
  };
  const auto standard = makers_.database_postgres_cluster;
  makers_.database_postgres_cluster = [standard](servicelib::Context context,
      servicelib::IServiceEnvironment& environment,
      const servicelib::config::PostgreSQLUserverDataConnectorConfig& config) {
    return userver::utils::Async("verify-query-postgres-maker", [standard, context, &environment, config] {
      auto cluster = standard(context, environment, config).Get();
      nativePostgres = cluster;
      if (const auto* expected = std::getenv("SA_QUERY_EXPECT_POOL_SIZE")) {
        require(config.connectionsCount == std::stoi(expected), "pool override missing in maker config");
        require(cluster->GetStatistics()->master.stats.connection.maximum ==
                    static_cast<unsigned>(config.connectionsCount), "native pool ignores resolved configuration");
      }
      return cluster;
    });
  };
}
void Service::customFunctionsInit(servicelib::Context) { return; }
void Service::serviceInit(servicelib::Context) { return; }
void Service::serviceStopping(servicelib::Context) noexcept { return; }
void Service::serviceStarted(servicelib::Context context) {
  const auto disposable = std::getenv("SA_QUERY_DISPOSABLE");
  require(disposable && std::string(disposable) == "1", "requires disposable stores");
  if (const auto* trust = std::getenv("SA_QUERY_S3_TLS_TRUSTED")) {
    require(std::string(trust) == "0" || std::string(trust) == "1", "invalid trust expectation");
    namespace s3 = servicelib::dataquery::s3;
    s3::HeadObject operation(nativeS3, "bucket");
    S3Probe<s3::HeadObjectRequest> handler{{"key"}};
    int state = 0;
    servicelib::dataquery::Collector<std::string> out(
        [](servicelib::MessageContext, servicelib::Payload<std::string>) {});
    bool denied = false;
    try {
      servicelib::dataquery::detail::runRequestTask(servicelib::MessageContext(context), [&] {
        operation.execute(servicelib::MessageContext(context), state, std::string{}, handler, out);
      }, std::chrono::seconds(5));
    } catch (const std::exception& error) {
      const std::string message(error.what());
      require(message.find("certificate") != std::string::npos || message.find("SSL") != std::string::npos,
              "expected TLS certificate error");
      denied = true;
    }
    require(denied == (std::string(trust) == "0"), "TLS trust outcome mismatch");
    require(handler.mapped == (denied ? 0 : 1), "TLS mapper count mismatch");
    nativePostgres.reset(); nativeS3.reset();
    std::cout << "QUERY_S3_TLS_PASSED trusted=" << trust << std::endl;
    userver::components::RequestStop();
    return;
  }
  if (std::getenv("SA_QUERY_POSTGRES_TLS_ONLY")) {
    servicelib::dataquery::postgres::Rows operation(nativePostgres, 7);
    NativeRowsProbe handler{"SELECT $1::text FROM pg_stat_ssl WHERE pid=pg_backend_pid() AND ssl"};
    int count = 0;
    std::vector<std::string> values;
    servicelib::dataquery::Collector<std::string> out(
        [&](servicelib::MessageContext, servicelib::Payload<std::string> value) {
          values.push_back(value.get());
        });
    servicelib::dataquery::detail::runRequestTask(servicelib::MessageContext(context), [&] {
      operation.execute(servicelib::MessageContext(context), count, std::string("encrypted"), handler, out);
    }, std::chrono::seconds(5));
    require(count == 1 && values == std::vector<std::string>{"encrypted"}, "TLS connection not encrypted");
    nativePostgres.reset();
    nativeS3.reset();
    std::cout << "QUERY_POSTGRES_TLS_PASSED" << std::endl;
    userver::components::RequestStop();
    return;
  }
  if (std::getenv("SA_QUERY_S3_LIFECYCLE_ONLY")) {
    checkNativeS3Endpoint(context);
    nativePostgres.reset(); nativeS3.reset();
    userver::components::RequestStop();
    return;
  }
  // The Compose runner provisions the schema and bucket before startup.
  checkNativeRows(context);
  checkNativeS3(context);

  const std::string binary("a\0b", 3);
  auto returned = invoke(context, getReturningRequestSubStream(), "returning-'key", binary, "returning");
  require(returned.size() == 2 && returned.front().value == binary, "RETURNING result mismatch");
  auto persisted = invoke(context, getRowsRequestSubStream(), "returning-'key", "", "returning-read");
  require(persisted.size() == 2 && persisted.front().value == binary, "RETURNING write not persisted");
  std::cout << "QUERY_LIVE_RETURNING_PASSED" << std::endl;
  invoke(context, getExecuteRequestSubStream(), "bound-'key", binary, "write");
  auto rows = invoke(context, getRowsRequestSubStream(), "bound-'key", "", "read");
  require(rows.size() == 2 && rows.front().value == binary, "PostgreSQL binary value mismatch");
  auto empty = invoke(context, getRowsRequestSubStream(), "absent", "", "empty");
  require(empty.size() == 1, "empty Rows must complete without a record");
  invoke(context, getPutObjectRequestSubStream(), "object", binary, "put");
  auto object = invoke(context, getGetObjectRequestSubStream(), "object", "", "get");
  std::string bytes;
  for (const auto& row : object) if (row.kind != "completed") bytes += row.value;
  require(bytes == binary, "S3 binary value mismatch");
  auto head = invoke(context, getHeadObjectRequestSubStream(), "object", "", "head");
  require(head.size() == 2, "HeadObject result missing");
  const auto metadata = userver::formats::json::FromString(head.front().value);
  require(metadata["size"].As<int>() == 3, "HeadObject size mismatch");
  auto listing = invoke(context, getListObjectsRequestSubStream(), "object", "", "list");
  require(listing.size() == 2, "ListObjects page missing");
  const auto entries = userver::formats::json::FromString(listing.front().value);
  require(entries.GetSize() == 1 && entries[0]["key"].As<std::string>() == "object",
          "ListObjects key mismatch");
  invoke(context, getDeleteObjectRequestSubStream(), "object", "", "delete");
  const auto afterDelete = invoke(context, getListObjectsRequestSubStream(), "object", "", "after-delete");
  require(afterDelete.size() == 2 &&
          userver::formats::json::FromString(afterDelete.front().value).GetSize() == 0,
          "DeleteObject did not remove the object");
  // Share the generated endpoints and a one-connection PostgreSQL pool across
  // concurrent graph calls. Each request must keep its own results/completion.
  std::vector<userver::engine::TaskWithResult<void>> requests;
  for (int index = 0; index < 8; ++index) {
    requests.push_back(userver::utils::Async("query-concurrent-live", [this, context, index] {
      const auto key = "concurrent-" + std::to_string(index);
      const std::string value = key + std::string("\0payload", 8);
      invoke(context, getExecuteRequestSubStream(), key, value, key + "-write");
      const auto records = invoke(context, getRowsRequestSubStream(), key, "", key + "-read");
      require(records.size() == 2 && records.front().value == value,
              "concurrent PostgreSQL results mixed or missing");
      invoke(context, getPutObjectRequestSubStream(), key, value, key + "-put");
      const auto results = invoke(context, getGetObjectRequestSubStream(), key, "", key + "-get");
      std::string body;
      for (const auto& result : results) if (result.kind != "completed") body += result.value;
      require(body == value, "concurrent S3 results mixed or missing");
      invoke(context, getDeleteObjectRequestSubStream(), key, "", key + "-delete");
    }));
  }
  for (auto& request : requests) request.Get();
  const auto remaining = invoke(context, getListObjectsRequestSubStream(), "concurrent-", "", "concurrent-cleanup");
  require(remaining.size() == 2 &&
          userver::formats::json::FromString(remaining.front().value).GetSize() == 0,
          "concurrent S3 cleanup incomplete");
  std::cout << "QUERY_LIVE_CONCURRENT_PASSED workers=8" << std::endl;
  std::cout << "QUERY_LIVE_ALL_SEVEN_PASSED" << std::endl;
  // The userver host owns signal handling; request normal process shutdown.
  userver::components::RequestStop();
  return;
}
}
