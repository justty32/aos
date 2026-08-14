#include "commands.hpp"

#include "aos/llm/agentloop.hpp"
#include "aos/llm/bot.hpp"
#include "aos/tooljson/spec.hpp"

#include <cstdlib>
#include <filesystem>
#include <format>
#include <string>
#include <vector>

namespace aos::builtin {
namespace {

// 設定從環境變數來，不從命令列 —— 因為金鑰絕對不該出現在 shell history 裡，
// 而端點和模型跟著金鑰走比較不會搞混。
[[nodiscard]] llm::LlmConfig config_from_environment() {
    llm::LlmConfig config;
    if (const char* url = std::getenv("AOS_LLM_URL");
        url != nullptr && *url != '\0') {
        config.url = url;
    }
    if (const char* model = std::getenv("AOS_LLM_MODEL");
        model != nullptr && *model != '\0') {
        config.model = model;
    }
    // key 不在這裡處理：Llm 自己會去讀 AOS_LLM_KEY／OPENAI_API_KEY，
    // 而且讀完就不再放進任何看得到的地方。
    return config;
}

// `aos llm ask` 的問題有兩個來源：命令列參數，和 stdin。兩個都給就接起來，
// 這樣 `cat log | aos llm ask 這段錯誤是什麼意思` 是能用的。
[[nodiscard]] asio::awaitable<std::string> collect_prompt(
    CommandContext& context) {
    std::string prompt;
    for (const std::string& word : context.operands()) {
        if (!prompt.empty()) {
            prompt += ' ';
        }
        prompt += word;
    }

    std::string piped;
    for (;;) {
        const auto chunk = co_await context.session.read_input();
        if (chunk.empty()) {
            break;
        }
        piped += chunk;
    }
    if (!piped.empty()) {
        prompt += prompt.empty() ? piped : std::format("\n\n{}", piped);
    }
    co_return prompt;
}

// AOS_LLM_TOOLS 是用 : 隔開的一串 .json，跟 PATH 一樣。沒設就是不給工具。
[[nodiscard]] std::vector<std::filesystem::path> tool_files() {
    std::vector<std::filesystem::path> files;
    const char* raw = std::getenv("AOS_LLM_TOOLS");
    if (raw == nullptr || *raw == '\0') {
        return files;
    }
    std::string_view rest{raw};
    while (!rest.empty()) {
        const auto colon = rest.find(':');
        const auto piece = rest.substr(0, colon);
        if (!piece.empty()) {
            files.emplace_back(piece);
        }
        if (colon == std::string_view::npos) {
            break;
        }
        rest.remove_prefix(colon + 1);
    }
    return files;
}

}  // namespace

asio::awaitable<std::int32_t> llm_ask(CommandContext& context) {
    const auto prompt = co_await collect_prompt(context);
    if (prompt.empty()) {
        co_await complain(context.session,
                          "用法：aos llm ask <問題>，或用管線把內容餵進來\n");
        co_return 2;
    }

    llm::ToolSet tools;
    if (const auto files = tool_files(); !files.empty()) {
        auto loaded = tooljson::load_tools(files);
        if (!loaded) {
            co_await complain(context.session,
                              std::format("工具載入失敗：{}\n", loaded.error()));
            co_return 2;
        }
        tools = std::move(*loaded);
    }

    llm::Bot bot{llm::Llm{config_from_environment()}, {}, std::move(tools)};

    // 邊收邊印。思考的部分走 stderr，答案走 stdout ——
    // 這樣 `aos llm ask ... > answer.txt` 拿到的是答案，思考仍然看得到。
    auto& session = context.session;
    llm::AgentOptions options{
        .on_part = [&session](llm::PartKind kind,
                              std::string_view text) -> asio::awaitable<void> {
            if (kind == llm::PartKind::think) {
                co_await session.write_error(text);
            } else {
                co_await session.write_output(text);
            }
        },
        .on_tool = [&session](const llm::ToolCall& call,
                              std::string_view output) -> asio::awaitable<void> {
            co_await session.write_error(
                std::format("\n[工具 {} → {} 個字元]\n", call.name, output.size()));
        },
    };

    const auto outcome = co_await llm::run_agent(bot, prompt, std::move(options));
    co_await say(context.session, "\n");

    if (!outcome) {
        co_await complain(context.session, std::format("{}\n", *outcome.err));
        co_return 1;
    }
    if (outcome.hit_step_limit) {
        co_await complain(
            context.session,
            std::format("（跑了 {} 步還沒結束，停在這裡）\n", outcome.steps));
        co_return 1;
    }
    co_return 0;
}

asio::awaitable<std::int32_t> llm_models(CommandContext& context) {
    llm::Llm engine{config_from_environment()};
    const auto names = co_await engine.models();

    if (names.empty()) {
        co_await complain(context.session,
                          "問不到模型清單（端點可能沒有 /model/info）\n");
        co_return 1;
    }
    std::string text;
    for (const std::string& name : names) {
        text += std::format("{}\n", name);
    }
    co_await say(context.session, std::move(text));
    co_return 0;
}

asio::awaitable<std::int32_t> llm_tools(CommandContext& context) {
    const auto files = tool_files();
    if (files.empty()) {
        co_await complain(context.session,
                          "AOS_LLM_TOOLS 沒設。它是用 : 隔開的一串 .json\n");
        co_return 2;
    }
    auto loaded = tooljson::load_tools(files);
    if (!loaded) {
        co_await complain(context.session, std::format("{}\n", loaded.error()));
        co_return 2;
    }
    std::string text;
    for (const auto& schema : loaded->schemas) {
        text += std::format("{}\n", schema.name);
    }
    co_await say(context.session, std::move(text));
    co_return 0;
}

}  // namespace aos::builtin
