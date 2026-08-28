#pragma once

#include <cstdint>
#include <string>

namespace aos::detail {

int run_exec_once(const char *folder, bool &did_work);
int run_exec_loop(const char *folder, std::uint64_t interval);
int run_init_world(const char *folder);
int run_deliver_world(const char *folder, const std::string &document);

}  // namespace aos::detail
