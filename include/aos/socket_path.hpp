#pragma once

#include <filesystem>

namespace aos {

// AOS_SOCKET 優先；其次使用 XDG_RUNTIME_DIR；最後才放在 /tmp。
[[nodiscard]] std::filesystem::path socket_path_from_environment();

}  // namespace aos
