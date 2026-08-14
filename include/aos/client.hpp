#pragma once

#include "aos/protocol.hpp"

#include <filesystem>

namespace aos {

[[nodiscard]] int run_client(Request request,
                             const std::filesystem::path& socket_path);

}  // namespace aos
