#pragma once

// run_blocking —— 把一段「會擋住」的同步程式碼搬到別的執行緒跑，用 co_await 等它。
//
// 為什麼需要它：daemon 的所有連線共用一條 io_context 執行緒。在那條執行緒上做
// 任何會擋的事（開子行程、讀大檔、算 hash），其他連線就一起停住。症狀是
// 「另一個終端的 aos ping 突然沒反應」，而且很難聯想到是這裡造成的。
//
//   const std::string output = co_await run_blocking([&] {
//       return run_a_subprocess(argv);   // 這一段在別的執行緒上跑
//   });
//   co_await session.write_output(output);   // 回到 io_context 執行緒
//
// co_await 回來之後就已經在 io_context 執行緒上了，所以後面可以放心碰
// session、runtime 那些沒有鎖的東西 —— 這正是這個包裝的重點：
// **把執行緒關在一個表達式裡**，不讓它擴散到整個程式。
//
// 兩件要注意的事：
//   1. lambda 裡不要碰 daemon 的共用狀態，那裡是另一條執行緒。要用的東西
//      先複製進去（像上面的 argv）。
//   2. 協程被取消時，這裡的解構會等那條執行緒跑完才回來。會擋很久的工作
//      要自己準備取消的辦法（例如子行程的 timeout）。

#include <asio/awaitable.hpp>
#include <asio/experimental/concurrent_channel.hpp>
#include <asio/this_coro.hpp>
#include <asio/use_awaitable.hpp>

#include <exception>
#include <optional>
#include <system_error>
#include <thread>
#include <type_traits>
#include <utility>

namespace aos {

template <typename Function>
[[nodiscard]] auto run_blocking(Function function)
    -> asio::awaitable<std::invoke_result_t<Function>> {
    using Result = std::invoke_result_t<Function>;
    static_assert(!std::is_void_v<Result>,
                  "run_blocking 要有回傳值；沒有的話回一個 bool 或 std::monostate");

    struct Slot {
        std::optional<Result> value;
        std::exception_ptr failure;
    };

    auto executor = co_await asio::this_coro::executor;
    // 容量 1，而且整趟只送一次，所以下面那個 try_send 一定會成功。
    asio::experimental::concurrent_channel<void(std::error_code, Slot)> channel{
        executor, 1};

    // jthread 活在這個協程的 frame 裡：協程還沒結束，它就還在，
    // 所以 lambda 用到的參考在它跑的時候一定有效。
    std::jthread worker{[&] {
        Slot slot;
        try {
            slot.value = function();
        } catch (...) {
            // 例外不能跨執行緒直接丟，先包起來，回到協程那側再原樣丟出。
            slot.failure = std::current_exception();
        }
        channel.try_send(std::error_code{}, std::move(slot));
    }};

    auto slot = co_await channel.async_receive(asio::use_awaitable);
    if (slot.failure) {
        std::rethrow_exception(slot.failure);
    }
    co_return std::move(*slot.value);
}

}  // namespace aos
