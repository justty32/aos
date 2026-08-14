#pragma once

#include <filesystem>

namespace aos {

[[nodiscard]] int run_daemon(const std::filesystem::path& socket_path);

}  // namespace aos
