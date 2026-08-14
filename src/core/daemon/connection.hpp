#pragma once

// aos_core 內部用的標頭：一條 client 連線的處理。

#include "aos/channel.hpp"
#include "aos/runtime.hpp"
#include "aos/session.hpp"

#include <asio/awaitable.hpp>

#include <exception>
#include <string>

namespace aos::detail {

// 把一條連線包成命令看得懂的 Session：stdin 訊框變成 read_input 的回傳值，
// 命令寫出來的東西立刻變成 stdout／stderr 訊框送回去，不在中間攢起來。
class ConnectionSession final : public Session {
public:
    explicit ConnectionSession(LocalSocket& socket) : socket_{socket} {}

    asio::awaitable<std::string> read_input() override;
    asio::awaitable<void> write_output(std::string_view text) override;
    asio::awaitable<void> write_error(std::string_view text) override;

    // 命令沒讀完的 stdin 要吃掉，否則 client 還在灌資料就收到 exit，
    // 會在寫入時拿到 EPIPE 而不是乾淨地結束。
    asio::awaitable<void> drain_input();

private:
    LocalSocket& socket_;
    bool input_ended_ = false;
};

// 一條連線的完整生命週期：讀 request_start、跑命令、回 exit。
asio::awaitable<void> serve(LocalSocket socket, Runtime& runtime);

// serve 丟出來的例外在這裡收尾。client 中途離線是正常的，不會吵。
void report_session_error(std::exception_ptr failure);

}  // namespace aos::detail
