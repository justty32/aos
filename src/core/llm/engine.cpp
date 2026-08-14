#include "aos/llm/engine.hpp"

#include "aos/llm/wire.hpp"
#include "llm/http.hpp"

#include <algorithm>
#include <cstdlib>
#include <format>
#include <utility>

namespace aos::llm {
namespace {

// 金鑰只從環境變數拿。寫死在設定檔裡的金鑰遲早會被 commit 進版本控制。
[[nodiscard]] std::string resolve_key(const std::string& given) {
    if (!given.empty()) {
        return given;
    }
    for (const char* name : {"AOS_LLM_KEY", "OPENAI_API_KEY"}) {
        if (const char* value = std::getenv(name);
            value != nullptr && *value != '\0') {
            return value;
        }
    }
    return "hello";  // 本機 proxy 多半不檢查，但欄位不能是空的
}

}  // namespace

Llm::Llm(LlmConfig config)
    : config_{std::move(config)}, key_{resolve_key(config_.key)} {
    // 原始設定裡的金鑰清掉，之後誰把 config 印出來都不會漏。
    config_.key.clear();
}

std::vector<std::string> Llm::headers() const {
    return {std::format("Authorization: Bearer {}", key_),
            "Content-Type: application/json"};
}

std::string Llm::completions_url() const {
    return std::format("{}/chat/completions", normalize_base_url(config_.url));
}

asio::awaitable<Caps> Llm::caps() {
    if (cached_) {
        co_return Caps::overlay(*cached_, config_.caps_override);
    }

    auto response = co_await detail::http_request({
        .url = std::format("{}/model/info", root_url(config_.url)),
        .headers = headers(),
        .timeout = std::chrono::seconds{5},
    });

    // 問不到就當成整表都是「不知道」。查不到不是錯誤 —— 不是每個端點都有
    // /model/info，而少了它並不影響講話。
    Caps remote;
    if (response.ok()) {
        const auto table = parse_model_info(response.body);
        const auto match = std::ranges::find(table, config_.model,
                                             &std::pair<std::string, Caps>::first);
        if (match != table.end()) {
            remote = match->second;
        }
    }
    cached_ = remote;
    co_return Caps::overlay(remote, config_.caps_override);
}

asio::awaitable<std::vector<std::string>> Llm::models() {
    auto response = co_await detail::http_request({
        .url = std::format("{}/model/info", root_url(config_.url)),
        .headers = headers(),
        .timeout = std::chrono::seconds{5},
    });
    std::vector<std::string> names;
    if (!response.ok()) {
        co_return names;
    }
    for (auto& [name, ignored] : parse_model_info(response.body)) {
        names.push_back(std::move(name));
    }
    std::ranges::sort(names);
    co_return names;
}

asio::awaitable<std::optional<std::string>> Llm::check(
    bool has_images, bool has_tools, std::string_view tool_choice) {
    if (!tool_choice.empty() && !has_tools) {
        co_return "給了 tool_choice，但這個 bot 沒有工具，不會有任何效果";
    }
    if (!has_images && !has_tools) {
        co_return std::nullopt;  // 純文字問答沒什麼好擋的，別為它去問端點
    }

    const Caps table = co_await caps();
    if (has_images && table.vision == false) {
        co_return std::format("模型 {} 不支援圖片輸入", config_.model);
    }
    if (has_tools && table.tools == false) {
        co_return std::format("模型 {} 不支援 tool calling", config_.model);
    }
    if (!tool_choice.empty() && table.tool_choice == false) {
        co_return std::format("模型 {} 不支援指定 tool_choice", config_.model);
    }
    co_return std::nullopt;
}

asio::awaitable<Reply> Llm::ask(Ask request) {
    const bool streaming = static_cast<bool>(request.on_part);

    auto payload = build_payload({
        .model = config_.model,
        .messages = request.messages,
        .tools = request.tools,
        .tool_choice = request.tool_choice,
        .stream = streaming,
        .params = &config_.params,
    });
    if (!payload) {
        Reply reply;
        reply.err = payload.error();
        co_return reply;
    }

    detail::HttpRequest http{
        .url = completions_url(),
        .headers = headers(),
        .body = std::move(*payload),
        .timeout = config_.timeout,
    };

    if (!streaming) {
        auto response = co_await detail::http_request(std::move(http));
        if (!response.error.empty()) {
            Reply reply;
            reply.err = std::format("連不上 {}：{}", config_.url, response.error);
            co_return reply;
        }
        // 狀態碼不對時 body 仍然是端點寫的錯誤 JSON，交給 parse_completion
        // 去讀出裡面那句話 —— 那句話通常比 "HTTP 400" 有用得多。
        Reply reply = parse_completion(response.body);
        if (!reply.err && response.status >= 300) {
            reply.err = std::format("HTTP {}：{}", response.status,
                                    response.body.substr(0, 500));
        }
        co_return reply;
    }

    StreamAccumulator accumulator;
    auto on_part = std::move(request.on_part);

    auto response = co_await detail::http_stream(
        std::move(http),
        // 這個 lambda 在 io_context 執行緒上跑，所以裡面 co_await 是安全的。
        [&accumulator, &on_part](
            std::string_view bytes) -> asio::awaitable<void> {
            for (const auto& part : accumulator.feed(bytes)) {
                co_await on_part(part.kind, part.text);
            }
        });

    Reply reply = accumulator.finish();
    if (!response.error.empty()) {
        // 傳輸斷在半路：已經收到的字仍然留在 reply 裡，因為那是真的說過的話。
        reply.err = std::format("串流中斷：{}", response.error);
    } else if (response.status >= 300) {
        reply.err = std::format("HTTP {}：{}", response.status,
                                response.body.substr(0, 500));
    }
    co_return reply;
}

}  // namespace aos::llm
