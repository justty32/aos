#pragma once

#include <filesystem>
#include <string>
#include <string_view>

namespace aos::tool::detail {

std::string read_text(const std::filesystem::path &path);
void atomic_write(const std::filesystem::path &path, std::string_view text);

}  // namespace aos::tool::detail
