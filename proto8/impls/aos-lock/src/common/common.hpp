// common.hpp：【common】aos-lock 跨元素共用的小東西（內部標頭，不對外）。
//
//   now_ms      現在（UTC epoch 毫秒）
//   parse_at    ISO 8601 UTC 到毫秒（aos-util 的 utc_now_ms 那種：2026-10-23T01:58:45.123+00:00，結尾也收 Z）→ epoch 毫秒；讀不懂 nullopt
#pragma once

#include "aos/lock.hpp"

#include <optional>
#include <string>

namespace aos::lock {

using aos::Error;
using aos::Json;

long long now_ms();
std::optional<long long> parse_at(const std::string& at);

}  // namespace aos::lock
