#include "aos/socket_path.hpp"

#include <cstdlib>
#include <format>
#include <optional>
#include <string_view>

#include <unistd.h>

namespace aos {
namespace {

// 空字串當成沒設定，避免 AOS_SOCKET= 這種寫法產生空路徑。
[[nodiscard]] std::optional<std::string_view> environment(const char* name) {
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') {
        return std::nullopt;
    }
    return std::string_view{value};
}

}  // namespace

std::filesystem::path socket_path_from_environment() {
    if (const auto path = environment("AOS_SOCKET")) {
        return std::filesystem::path{*path};
    }
    if (const auto directory = environment("XDG_RUNTIME_DIR")) {
        return std::filesystem::path{*directory} / "aos.sock";
    }
    // 最後才落到 /tmp，檔名帶 uid 以免多個使用者互相撞到。
    return std::filesystem::path{"/tmp"} / std::format("aos-{}.sock", ::getuid());
}

}  // namespace aos
