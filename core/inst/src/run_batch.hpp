#pragma once

#include <string>

namespace aos::detail {

int execute_batch(const std::string &buffer, const char *source);

}  // namespace aos::detail
