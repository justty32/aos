#include "socket_setup.hpp"

#include "aos/channel.hpp"

#include <asio/local/stream_protocol.hpp>

#include <cerrno>
#include <format>
#include <optional>
#include <stdexcept>
#include <system_error>

#include <sys/stat.h>

namespace aos::detail {
namespace {

// 需要 st_uid 才能確認 socket 是自己的，所以用 lstat 而不是 std::filesystem。
[[nodiscard]] std::optional<struct ::stat>
path_status(const std::filesystem::path& path) {
    struct ::stat status{};
    if (::lstat(path.c_str(), &status) == 0) {
        return status;
    }
    if (errno == ENOENT) {
        return std::nullopt;
    }
    throw std::system_error{errno, std::generic_category(),
                            "檢查 socket 路徑失敗"};
}

}  // namespace

void prepare_socket_path(asio::io_context& context,
                         const std::filesystem::path& path) {
    const auto status = path_status(path);
    if (!status) {
        return;
    }
    if (!S_ISSOCK(status->st_mode) || status->st_uid != ::getuid()) {
        throw std::runtime_error{std::format(
            "既有路徑不是目前使用者擁有的 socket：{}", path.string())};
    }

    // 連得上代表另一個 daemon 還活著；連線被拒才是可以清掉的殘留檔。
    LocalSocket probe{context};
    std::error_code error;
    probe.connect(asio::local::stream_protocol::endpoint{path.string()}, error);
    if (!error) {
        throw std::runtime_error{
            std::format("已有 aos-daemon 正在監聽 {}", path.string())};
    }
    if (error != asio::error::connection_refused) {
        throw std::system_error{error, "檢查既有 socket 失敗"};
    }
    if (::unlink(path.c_str()) < 0) {
        throw std::system_error{errno, std::generic_category(),
                                "移除殘留 socket 失敗"};
    }
}

}  // namespace aos::detail
