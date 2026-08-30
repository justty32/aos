#pragma once

#include <filesystem>
#include <string_view>

namespace aos::agent::cli {

int run_listen(const std::filesystem::path &folder, std::string_view name,
               bool once);
int run_talk(const std::filesystem::path &folder, std::string_view name);

}  // namespace aos::agent::cli
