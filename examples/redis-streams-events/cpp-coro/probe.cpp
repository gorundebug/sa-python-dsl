// Test peer only: business processing lives in the generated graph.
#include <cstdlib>
#include <hiredis/hiredis.h>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
using Reply = std::unique_ptr<redisReply, decltype(&freeReplyObject)>;
std::string env(const char *name, const char *fallback = "") {
  const auto value = std::getenv(name);
  return value ? value : fallback;
}
Reply command(redisContext *c, std::vector<std::string> args) {
  std::vector<const char *> argv;
  std::vector<size_t> lengths;
  for (const auto &arg : args) {
    argv.push_back(arg.data());
    lengths.push_back(arg.size());
  }
  Reply reply(static_cast<redisReply *>(redisCommandArgv(
                  c, argv.size(), argv.data(), lengths.data())),
              freeReplyObject);
  if (!reply || reply->type == REDIS_REPLY_ERROR)
    throw std::runtime_error("test peer command failed");
  return reply;
}
std::string hex(const redisReply *value) {
  if (value->type != REDIS_REPLY_STRING)
    throw std::runtime_error("expected binary string");
  std::string out;
  const char *digits = "0123456789abcdef";
  for (size_t i = 0; i < value->len; ++i) {
    auto b = static_cast<unsigned char>(value->str[i]);
    out += digits[b >> 4];
    out += digits[b & 15];
  }
  return out;
}
int main(int argc, char **argv) try {
  if (argc != 4)
    throw std::runtime_error("mode input output required");
  timeval timeout{2, 0};
  std::unique_ptr<redisContext, decltype(&redisFree)> c(
      redisConnectWithTimeout(env("PEER_HOST", "host.docker.internal").c_str(),
                              std::stoi(env("PEER_PORT", "16379")), timeout),
      redisFree);
  if (!c || c->err)
    throw std::runtime_error("test peer connection failed");
  redisSetTimeout(c.get(), timeout);
  const auto password = env("REDIS_STREAMS_TEST_PASSWORD", "adapter-test");
  if (!password.empty())
    command(c.get(), {"AUTH", password});
  std::string mode = argv[1], input = argv[2], output = argv[3];
  if (mode == "ready") {
    auto r = command(c.get(), {"XINFO", "GROUPS", input});
    bool found = false;
    for (size_t i = 0; i < r->elements; i++)
      for (size_t j = 0; j + 1 < r->element[i]->elements; j += 2) {
        auto k = r->element[i]->element[j];
        auto v = r->element[i]->element[j + 1];
        if (std::string(k->str, k->len) == "name" &&
            std::string(v->str, v->len) == "event_processors")
          found = true;
      }
    if (!found)
      return 2;
  } else if (mode == "seed") {
    for (int i = 0; i < 3; i++)
      command(c.get(),
              {"XADD", input, "*", "ID", "event-" + std::to_string(i), "Value",
               " hello ", "opaque", std::string("\0\xff", 2), "opaque",
               "second", "x-stream-id", "source-event-" + std::to_string(i)});
  } else if (mode == "observe") {
    auto r = command(c.get(), {"XRANGE", output, "-", "+"});
    for (size_t i = 0; i < r->elements; i++) {
      auto row = r->element[i];
      std::cout << hex(row->element[0]);
      auto fields = row->element[1];
      for (size_t j = 0; j < fields->elements; j++)
        std::cout << '\t' << hex(fields->element[j]);
      std::cout << '\n';
    }
  } else if (mode == "pending") {
    auto r = command(c.get(), {"XPENDING", input, "event_processors"});
    std::cout << r->element[0]->integer << '\n';
  } else if (mode == "clean")
    command(c.get(), {"DEL", input, output});
  else
    throw std::runtime_error("invalid peer mode");
  return 0;
} catch (const std::exception &error) {
  std::cerr << error.what() << '\n';
  return 1;
}
