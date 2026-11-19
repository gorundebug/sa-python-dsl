// Test-only replacement for the generated service extension, never production code.
#include "storageworker/internal/app/service.hpp"
#include <aws/s3/S3Client.h>
#include <aws/s3/model/CreateBucketRequest.h>
#include <aws/s3/model/HeadObjectRequest.h>
#include <algorithm>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <vector>

namespace storage_query::storage_worker::app {
namespace {
using Request = types::StorageRequest;
using Result = types::StorageResult;
void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
boost::asio::awaitable<std::vector<Result>> invoke(
    servicelib::Context parent, std::shared_ptr<servicelib::ISubStream<Request, Result>> entry,
    std::string key, std::string value, std::string id) {
  struct Output { std::mutex mutex; std::vector<Result> rows; };
  auto output = std::make_shared<Output>();
  auto collector = std::make_shared<servicelib::SubStreamCollectorFunc<Result>>(
      [output](servicelib::MessageContext, const Result& row) -> boost::asio::awaitable<bool> {
        std::lock_guard lock(output->mutex);
        output->rows.push_back(row);
        co_return row.kind == "completed";
      });
  auto context = servicelib::MessageContext(parent).withDeadline(
      std::chrono::steady_clock::now() + std::chrono::seconds(10));
  auto request = servicelib::Payload<Request>::make(Request{id, key, value});
  co_await entry->consume(context, request, collector);
  std::lock_guard lock(output->mutex);
  require(std::count_if(output->rows.begin(), output->rows.end(),
      [](const auto& row) { return row.kind == "completed"; }) == 1, "expected one completion");
  require(std::all_of(output->rows.begin(), output->rows.end(),
      [&](const auto& row) { return row.requestId == id; }), "request correlation mismatch");
  co_return output->rows;
}
}
boost::asio::awaitable<void> Service::customMakersInit(servicelib::Context) { co_return; }
boost::asio::awaitable<void> Service::customFunctionsInit(servicelib::Context) { co_return; }
boost::asio::awaitable<void> Service::serviceInit(servicelib::Context) { co_return; }
boost::asio::awaitable<void> Service::serviceStopping(servicelib::Context) { co_return; }
boost::asio::awaitable<void> Service::serviceStarted(servicelib::Context context) {
  const auto disposable = std::getenv("SA_QUERY_DISPOSABLE");
  require(disposable && std::string(disposable) == "1", "requires disposable stores");
  // Fixture provisioning only. Operations under test use generated default makers.
  Aws::Client::ClientConfiguration cfg;
  cfg.region = "us-east-1";
  cfg.endpointOverride = std::getenv("OBJECTS_ADDRESS");
  Aws::S3::S3Client setup(cfg, Aws::Client::AWSAuthV4Signer::PayloadSigningPolicy::Never, false);
  Aws::S3::Model::CreateBucketRequest bucket;
  bucket.SetBucket("query-example");
  require(setup.CreateBucket(bucket).IsSuccess(), "fixture bucket creation failed");

  const std::string binary("a\0b", 3);
  auto returned = co_await invoke(context, getReturningRequestSubStream(), "returning-'key", binary, "returning");
  require(returned.size() == 2 && returned.front().value == binary, "RETURNING result mismatch");
  auto persisted = co_await invoke(context, getRowsRequestSubStream(), "returning-'key", "", "returning-read");
  require(persisted.size() == 2 && persisted.front().value == binary, "RETURNING write not persisted");
  std::cout << "QUERY_LIVE_RETURNING_PASSED" << std::endl;
  co_await invoke(context, getExecuteRequestSubStream(), "bound-'key", binary, "write");
  auto rows = co_await invoke(context, getRowsRequestSubStream(), "bound-'key", "", "read");
  require(rows.size() == 2 && rows.front().value == binary, "PostgreSQL binary value mismatch");
  auto empty = co_await invoke(context, getRowsRequestSubStream(), "absent", "", "empty");
  require(empty.size() == 1, "empty Rows must complete without a record");
  co_await invoke(context, getPutObjectRequestSubStream(), "object", binary, "put");
  auto object = co_await invoke(context, getGetObjectRequestSubStream(), "object", "", "get");
  std::string bytes;
  for (const auto& row : object) if (row.kind != "completed") bytes += row.value;
  require(bytes == binary, "S3 binary value mismatch");
  auto head = co_await invoke(context, getHeadObjectRequestSubStream(), "object", "", "head");
  require(head.size() == 2, "HeadObject result missing");
  auto listing = co_await invoke(context, getListObjectsRequestSubStream(), "object", "", "list");
  require(listing.size() > 1, "ListObjects page missing");
  co_await invoke(context, getDeleteObjectRequestSubStream(), "object", "", "delete");
  Aws::S3::Model::HeadObjectRequest deleted;
  deleted.SetBucket("query-example"); deleted.SetKey("object");
  require(!setup.HeadObject(deleted).IsSuccess(), "DeleteObject did not delete the object");
  std::cout << "QUERY_LIVE_ALL_SEVEN_PASSED" << std::endl;
  // Generated main already installed its signal handler; exercise normal shutdown.
  std::raise(SIGTERM);
  co_return;
}
}
