#pragma once

#include <sys/types.h>

namespace aos::exec::detail {

void register_running(pid_t pid);
void unregister_running(pid_t pid);

}  // namespace aos::exec::detail
