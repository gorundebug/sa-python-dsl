#pragma once
#include <string>
namespace pulsar_events::event_processor::types {
struct Event final {
  std::string ID;
  std::string Value;
};
} // namespace pulsar_events::event_processor::types
