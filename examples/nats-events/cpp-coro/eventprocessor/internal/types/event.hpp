#pragma once
#include <string>
namespace nats_events::event_processor::types {
struct Event final { std::string ID; std::string Value; };
}
