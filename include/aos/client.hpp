#pragma once

#include "aos/protocol.hpp"

#include <filesystem>

namespace aos {

// 送出 request 後，stdin 的轉送跟輸出的接收是同時進行的，
// 所以 stdin 還沒結束就能看到 daemon 的輸出。回傳命令的 exit code。
[[nodiscard]] int run_client(const Request& request,
                             const std::filesystem::path& socket_path);

}  // namespace aos
