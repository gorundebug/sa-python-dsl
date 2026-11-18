#pragma once
#include <string>
namespace redis_streams_events::event_processor::types {
struct Event final {
  std::string ID;
  std::string Value;
};
} // namespace redis_streams_events::event_processor::types
