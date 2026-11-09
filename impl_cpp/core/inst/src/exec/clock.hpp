// clock.hpp：單調時鐘毫秒、睡眠、ISO8601 現在時刻（搬自 archive/aos-v1/core/exec，行為不改）。
#pragma once

#include <cstdint>

namespace aos::exec::detail {

std::uint64_t monotonic_ms();
void sleep_ms(std::uint64_t milliseconds);

}  // namespace aos::exec::detail
