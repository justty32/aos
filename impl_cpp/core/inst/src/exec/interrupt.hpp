// interrupt.hpp：已 fork 未收線的子行程登記表，interrupt_running 對它們的 process group 送訊號（async-signal-safe）（搬自 archive/aos-v1/core/exec，行為不改）。
#pragma once

#include <sys/types.h>

namespace aos::exec::detail {

void register_running(pid_t pid);
void unregister_running(pid_t pid);

}  // namespace aos::exec::detail
