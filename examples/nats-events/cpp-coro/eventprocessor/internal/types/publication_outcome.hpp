#pragma once
#include <string>
namespace nats_events::event_processor::types {
struct PublicationOutcome final { std::string EventID; bool Accepted{}; std::string Reason; };
}
