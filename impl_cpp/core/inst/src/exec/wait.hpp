// wait.hpp：waitpid 的重試包裝與有期限的等待（搬自 archive/aos-v1/core/exec，行為不改）。
#pragma once

#include <cstdint>

#include <sys/types.h>

namespace aos::exec::detail {

pid_t wait_retry(pid_t pid, int *status, int options);
bool wait_until(pid_t pid, std::uint64_t limit_ms, int &raw_status, int &error);

}  // namespace aos::exec::detail
