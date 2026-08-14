#include "input.hpp"

#include <asio/buffer.hpp>
#include <asio/posix/stream_descriptor.hpp>
#include <asio/redirect_error.hpp>
#include <asio/use_awaitable.hpp>

#include <array>
#include <cerrno>
#include <cstddef>
#include <exception>
#include <print>
#include <string_view>
#include <system_error>

#include <sys/stat.h>
#include <unistd.h>

namespace aos::detail {
namespace {

// epoll 不收一般檔案跟目錄。反正它們讀取本來就不會阻塞，那條路走同步 read。
[[nodiscard]] bool can_be_polled(int descriptor) {
    struct ::stat status{};
    if (::fstat(descriptor, &status) < 0) {
        return false;
    }
    return !S_ISREG(status.st_mode) && !S_ISDIR(status.st_mode);
}

// pipe、terminal、socket 走 asio，等待期間不會卡住收輸出的那條 coroutine。
asio::awaitable<void> forward_pollable(LocalSocket& socket,
                                       asio::posix::stream_descriptor input) {
    std::array<char, stream_chunk_size> buffer{};
    while (true) {
        std::error_code error;
        const auto count = co_await input.async_read_some(
            asio::buffer(buffer),
            asio::redirect_error(asio::use_awaitable, error));
        if (error == asio::error::eof) {
            co_return;
        }
        if (error) {
            throw std::system_error{error, "讀取 stdin 失敗"};
        }
        // buffer 在這個 coroutine frame 裡，撐得過下面的 co_await。
        co_await write_frame(socket, FrameKind::stdin_chunk,
                             std::string_view{buffer.data(), count});
    }
}

// 一般檔案：read 立刻回，中間的 co_await write_frame 仍然會讓出執行權，
// 所以收輸出的 coroutine 不會被大檔案餓死。
asio::awaitable<void> forward_file(LocalSocket& socket, int descriptor) {
    std::array<char, stream_chunk_size> buffer{};
    while (true) {
        const auto count = ::read(descriptor, buffer.data(), buffer.size());
        if (count < 0) {
            if (errno == EINTR) {
                continue;
            }
            throw std::system_error{errno, std::generic_category(),
                                    "讀取 stdin 失敗"};
        }
        if (count == 0) {
            co_return;
        }
        co_await write_frame(
            socket, FrameKind::stdin_chunk,
            std::string_view{buffer.data(), static_cast<std::size_t>(count)});
    }
}

}  // namespace

asio::awaitable<void> forward_standard_input(LocalSocket& socket) {
    // 直接從終端呼叫時不該卡在等 EOF，立刻宣告 stdin 結束。
    if (::isatty(STDIN_FILENO) == 0) {
        if (can_be_polled(STDIN_FILENO)) {
            // stream_descriptor 會關掉自己拿到的 fd，所以複製一份，
            // 免得順手關掉真正的 stdin。
            const int copy = ::dup(STDIN_FILENO);
            if (copy < 0) {
                throw std::system_error{errno, std::generic_category(),
                                        "複製 stdin 失敗"};
            }
            const auto executor = co_await asio::this_coro::executor;
            co_await forward_pollable(
                socket, asio::posix::stream_descriptor{executor, copy});
        } else {
            co_await forward_file(socket, STDIN_FILENO);
        }
    }
    co_await write_frame(socket, FrameKind::stdin_end, {});
}

void report_input_failure(std::exception_ptr failure) {
    if (!failure) {
        return;
    }
    try {
        std::rethrow_exception(failure);
    } catch (const std::system_error& error) {
        // daemon 先結束時這條 coroutine 會撞到 EPIPE，那不是使用者的問題。
        if (error.code() != asio::error::broken_pipe &&
            error.code() != asio::error::operation_aborted) {
            std::println(stderr, "aos：{}", error.what());
        }
    } catch (const std::exception& error) {
        std::println(stderr, "aos：{}", error.what());
    }
}

}  // namespace aos::detail
