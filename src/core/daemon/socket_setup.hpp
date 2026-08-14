#pragma once

// aos_core 內部用的標頭：監聽用 socket 檔的準備與清理。

#include <asio/io_context.hpp>

#include <filesystem>
#include <utility>

#include <unistd.h>

namespace aos::detail {

// 監聽用的 socket 檔在 daemon 結束時要清掉，不然下次啟動會看到殘留。
class SocketPathGuard {
public:
    explicit SocketPathGuard(std::filesystem::path path)
        : path_{std::move(path)} {}
    ~SocketPathGuard() { ::unlink(path_.c_str()); }

    SocketPathGuard(const SocketPathGuard&) = delete;
    SocketPathGuard& operator=(const SocketPathGuard&) = delete;

private:
    std::filesystem::path path_;
};

// 確認這個路徑可以拿來監聽：沒東西就直接用；有殘留的死 socket 就清掉；
// 有別的 daemon 活著、或那不是自己的 socket，就丟例外。
void prepare_socket_path(asio::io_context& context,
                         const std::filesystem::path& path);

}  // namespace aos::detail
