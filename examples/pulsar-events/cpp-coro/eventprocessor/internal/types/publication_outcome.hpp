#pragma once
#include <string>
namespace pulsar_events::event_processor::types {
struct PublicationOutcome final {
  std::string EventID;
  std::string MessageID;
  bool Accepted{};
  std::string Reason;
};
} // namespace pulsar_events::event_processor::types
