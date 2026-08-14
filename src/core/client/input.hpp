#pragma once

// aos_core 內部用的標頭：把本機 stdin 轉送成 stdin_chunk 訊框。

#include "aos/channel.hpp"

#include <asio/awaitable.hpp>

#include <exception>

namespace aos::detail {

// 一路讀到 EOF，最後補一個 stdin_end。stdin 是終端時不等 EOF，直接收尾。
// 這個 coroutine 跟接收輸出的那條同時跑，所以 stdin 還開著也看得到輸出。
asio::awaitable<void> forward_standard_input(LocalSocket& socket);

// forward_standard_input 丟出來的例外在這裡收尾。
void report_input_failure(std::exception_ptr failure);

}  // namespace aos::detail
