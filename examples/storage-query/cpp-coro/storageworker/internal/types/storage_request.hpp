#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace storage_query::storage_worker::types {

struct StorageRequest final { std::string requestId; std::string key; std::string value; };

}  // namespace storage_query::storage_worker::types
