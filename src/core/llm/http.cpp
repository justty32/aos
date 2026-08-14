#include "http.hpp"

#include <asio/experimental/concurrent_channel.hpp>
#include <asio/this_coro.hpp>
#include <asio/use_awaitable.hpp>

#include <curl/curl.h>

#include <mutex>
#include <thread>
#include <utility>

namespace aos::llm::detail {
namespace {

// curl_global_init 必須在任何 easy handle 之前跑，而且只跑一次。
void ensure_curl_ready() {
    static std::once_flag once;
    std::call_once(once, [] { ::curl_global_init(CURL_GLOBAL_DEFAULT); });
}

// 一段從 worker 送回協程的東西。done 代表整趟結束，result 才有意義。
struct Piece {
    std::string chunk;
    bool done = false;
    HttpResponse result;
};

using Channel =
    asio::experimental::concurrent_channel<void(std::error_code, Piece)>;

// worker 端送資料。channel 滿了就等一下再試 —— 這就是背壓：
// 協程還沒把上一段處理完，curl 就先停在這裡不再往下收。
// 傳 const& 而不是 move：失敗時要能原封不動再試一次，被搬走就沒得試了。
void push(Channel& channel, const Piece& piece) {
    while (!channel.try_send(std::error_code{}, piece)) {
        std::this_thread::sleep_for(std::chrono::milliseconds{1});
    }
}

// 寫入回呼共用的狀態。串流與否的差別只在這裡。
struct WriteContext {
    CURL* handle = nullptr;
    Channel* channel = nullptr;  // nullptr 代表不串流，全部收進 sink
    std::string* sink = nullptr;
    long status = 0;  // 第一次寫入時才問得到
};

std::size_t on_write(char* data, std::size_t size, std::size_t count,
                     void* user_data) {
    const std::size_t total = size * count;
    auto* context = static_cast<WriteContext*>(user_data);

    if (context->status == 0) {
        // header 已經收完才會走到寫入，所以這裡問得到狀態碼。
        ::curl_easy_getinfo(context->handle, CURLINFO_RESPONSE_CODE,
                            &context->status);
    }

    const bool failed = context->status < 200 || context->status >= 300;
    if (context->channel == nullptr || failed) {
        // 失敗的回應不是串流內容，是一段錯誤 JSON。餵給 SSE 解析器只會得到
        // 「解析不出東西」，真正的原因反而不見了，所以改留在 body 裡。
        if (context->sink != nullptr) {
            context->sink->append(data, total);
        }
        return total;
    }

    push(*context->channel, Piece{.chunk = std::string{data, total}});
    return total;
}

// 實際去跑的那一段，在 worker thread 上。
HttpResponse perform(const HttpRequest& request, Channel* channel,
                     std::string& sink) {
    ensure_curl_ready();
    HttpResponse response;

    CURL* handle = ::curl_easy_init();
    if (handle == nullptr) {
        response.error = "curl_easy_init 失敗";
        return response;
    }

    WriteContext write_context{
        .handle = handle, .channel = channel, .sink = &sink};

    ::curl_slist* headers = nullptr;
    for (const std::string& header : request.headers) {
        headers = ::curl_slist_append(headers, header.c_str());
    }

    ::curl_easy_setopt(handle, CURLOPT_URL, request.url.c_str());
    ::curl_easy_setopt(handle, CURLOPT_HTTPHEADER, headers);
    ::curl_easy_setopt(handle, CURLOPT_WRITEFUNCTION, &on_write);
    ::curl_easy_setopt(handle, CURLOPT_WRITEDATA, &write_context);
    ::curl_easy_setopt(handle, CURLOPT_TIMEOUT,
                       static_cast<long>(request.timeout.count()));
    ::curl_easy_setopt(handle, CURLOPT_FOLLOWLOCATION, 1L);
    // 這條 handle 只給這一次呼叫用，不共用，也不想讓 curl 去動 signal。
    ::curl_easy_setopt(handle, CURLOPT_NOSIGNAL, 1L);
    if (!request.body.empty()) {
        ::curl_easy_setopt(handle, CURLOPT_POSTFIELDS, request.body.c_str());
        ::curl_easy_setopt(handle, CURLOPT_POSTFIELDSIZE,
                           static_cast<long>(request.body.size()));
    }

    const CURLcode code = ::curl_easy_perform(handle);
    if (code == CURLE_OK) {
        ::curl_easy_getinfo(handle, CURLINFO_RESPONSE_CODE, &response.status);
    } else {
        response.error = ::curl_easy_strerror(code);
    }

    ::curl_slist_free_all(headers);
    ::curl_easy_cleanup(handle);
    return response;
}

}  // namespace

asio::awaitable<HttpResponse> http_request(HttpRequest request) {
    auto executor = co_await asio::this_coro::executor;
    Channel channel{executor, 1};

    std::string body;
    // jthread 活在這個協程的 frame 裡：協程沒結束它就還在，
    // 所以 body 與 channel 的位址在 worker 用它們的時候一定有效。
    std::jthread worker{[&] {
        auto result = perform(request, nullptr, body);
        result.body = std::move(body);
        push(channel, Piece{.done = true, .result = std::move(result)});
    }};

    auto piece = co_await channel.async_receive(asio::use_awaitable);
    co_return std::move(piece.result);
}

asio::awaitable<HttpResponse> http_stream(HttpRequest request,
                                          ChunkHandler on_chunk) {
    auto executor = co_await asio::this_coro::executor;
    // 緩衝 64 段：夠讓 curl 不必每收一段就等一次，又不會無上限地囤在記憶體裡。
    Channel channel{executor, 64};

    std::string failure_body;  // 狀態碼不對時，回應內容會落到這裡
    std::jthread worker{[&] {
        auto result = perform(request, &channel, failure_body);
        result.body = std::move(failure_body);
        push(channel, Piece{.done = true, .result = std::move(result)});
    }};

    for (;;) {
        auto piece = co_await channel.async_receive(asio::use_awaitable);
        if (piece.done) {
            co_return std::move(piece.result);
        }
        co_await on_chunk(piece.chunk);
    }
}

}  // namespace aos::llm::detail
