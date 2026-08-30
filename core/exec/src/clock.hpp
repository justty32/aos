#pragma once

#include <cstdint>

namespace aos::exec::detail {

std::uint64_t monotonic_ms();
void sleep_ms(std::uint64_t milliseconds);

}  // namespace aos::exec::detail
