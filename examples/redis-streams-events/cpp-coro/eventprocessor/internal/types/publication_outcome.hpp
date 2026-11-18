#pragma once
#include <string>
namespace redis_streams_events::event_processor::types {
struct PublicationOutcome final {
  std::string EventID;
  std::string EntryID;
  bool Accepted{};
  std::string Reason;
};
} // namespace redis_streams_events::event_processor::types
