#pragma once
#include <userver/engine/task/task_with_result.hpp>
#include <userver/utils/async.hpp>
#include <algorithm>
#include <cctype>

#include <chrono>
#include <cstddef>
#include <memory>
#include <stdexcept>
#include <tuple>
#include <utility>
#include <vector>

#include <eventprocessor/internal/types/event.hpp>

#include <servicelib/runtime/base.hpp>
#include <servicelib/runtime/common.hpp>
#include <servicelib/runtime/config/stream_types.hpp>
#include <servicelib/runtime/consumer.hpp>
#include <servicelib/runtime/context.hpp>
#include <servicelib/runtime/environment/environment.hpp>

namespace pulsar_events::event_processor::functions {

// User-owned callable. Its operator is checked by servicelib::StreamFunction
// when the generated stream graph binds it to an operator.
struct NormalizeEvent final {
  template <typename Output>
  void
  operator()(servicelib::MessageContext context, servicelib::StreamBase &stream,
             const pulsar_events::event_processor::types::Event &value,
             Output &&out) const {
    (void)stream;
    auto normalized = value;
    const auto begin = normalized.Value.find_first_not_of(" \t\r\n");
    const auto end = normalized.Value.find_last_not_of(" \t\r\n");
    normalized.Value = begin == std::string::npos
                           ? ""
                           : normalized.Value.substr(begin, end - begin + 1);
    std::transform(normalized.Value.begin(), normalized.Value.end(),
                   normalized.Value.begin(), [](unsigned char c) {
                     return static_cast<char>(std::toupper(c));
                   });
    out.out(std::move(context), std::move(normalized));
  }
};

inline userver::engine::TaskWithResult<std::unique_ptr<NormalizeEvent>>
MakeNormalizeEvent(servicelib::Context context,
  servicelib::IServiceEnvironment& environment) {
  return userver::utils::Async("make-NormalizeEvent",
      [context = std::move(context), &environment] {
        (void)context; (void)environment;
        return std::make_unique<NormalizeEvent>();
      });
}

} // namespace pulsar_events::event_processor::functions