#pragma once

// libcurl 包成 awaitable。這是整個專案裡唯一一處「協程 ↔ 執行緒」的接縫，
// 所以講清楚它為什麼長這樣。
//
// 問題：libcurl 的 easy interface 是同步的，curl_easy_perform() 會一路擋到收完。
// 在 io_context 的執行緒上直接呼叫它，daemon 的其他連線就全部凍住了。
//
// 解法：把 perform 丟到一條 worker thread，用 asio 的 concurrent_channel 把結果
// 送回來。channel 是**跨執行緒安全**的那一種（concurrent_channel 而不是 channel），
// worker 端用 try_send（不阻塞、可以在非 asio 執行緒上呼叫），協程端用
// async_receive 等。這樣：
//
//   io_context 執行緒        worker 執行緒
//   ─────────────────        ─────────────
//   co_await receive  ←──┐
//                        │ try_send(一段回應)
//                        │ curl_easy_perform() 在這裡擋著
//
// 於是「有一條執行緒在擋」這件事被關在 worker 裡，io_context 完全不受影響。
//
// 為什麼不用 curl 的 multi interface 接 asio 的 reactor：那要自己接管 socket
// 的註冊與時鐘，程式碼會多好幾倍，而且錯了很難查。HTTP 呼叫本來就是低頻的
// （一次對話幾次），一條 thread 換掉那整包複雜度很划算。
//
// 生命週期：worker 是 std::jthread，活在協程的 frame 裡，協程結束時才 join。
// 所以協程還在，thread 就一定還在，callback 不會寫到已經死掉的東西。
// 代價是協程被取消時，解構的 join 會等 curl 跑完（最多到 timeout）。

#include <asio/awaitable.hpp>

#include <chrono>
#include <functional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::llm::detail {

struct HttpRequest {
    std::string url;
    std::vector<std::string> headers;  // "Name: value"

    // 空的就是 GET，有東西就是 POST。
    std::string body;

    std::chrono::seconds timeout{120};
};

struct HttpResponse {
    long status = 0;

    // 串流模式下這裡是空的（內容都已經交給 ChunkHandler 了），
    // 除非 status 不是 2xx —— 那時候 body 是錯誤訊息，要留著給人看。
    std::string body;

    // 傳輸層壞掉（連不上、DNS、逾時）。空字串代表傳輸本身成功，
    // 但 status 仍然可能是 400。
    std::string error;

    [[nodiscard]] bool ok() const {
        return error.empty() && status >= 200 && status < 300;
    }
};

// 一次收完。
[[nodiscard]] asio::awaitable<HttpResponse> http_request(HttpRequest request);

// 收到的每一段原始位元組。在 io_context 執行緒上跑，所以裡面可以放心 co_await。
using ChunkHandler = std::function<asio::awaitable<void>(std::string_view)>;

// 邊收邊交。回傳值的 body 只在失敗時有東西。
[[nodiscard]] asio::awaitable<HttpResponse> http_stream(HttpRequest request,
                                                        ChunkHandler on_chunk);

}  // namespace aos::llm::detail
