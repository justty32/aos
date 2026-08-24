#pragma once

#include <cstdint>

namespace aos::detail {

int run_exec_once(const char *folder, bool &did_work);
int run_exec_loop(const char *folder, std::uint64_t interval);
int run_init_world(const char *folder);

}  // namespace aos::detail
