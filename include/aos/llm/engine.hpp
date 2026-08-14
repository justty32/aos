#pragma once

// Llm —— 思考引擎：端點、模型、旋鈕，以及那個端點做得到什麼。
//
// 人格（system）和記憶（history）不在這裡，在 Bot（bot.hpp）。分開的理由是
// 「拿什麼在想」和「它是誰」會各自變動 —— 同一個 bot 換一顆模型繼續講很常見，
// 換完記憶還在。Bot 是**整顆拿著**一個 Llm（不是共用一份），所以要換就
// `bot.llm().set_model("...")`，或直接指派一個新的進去。
//
//   Llm engine{{.model = "deepseek-chat", .url = "http://localhost:4000"}};
//   Reply reply = co_await engine.ask({.messages = history});
//
// 金鑰**只從環境變數讀**，而且不會出現在任何錯誤訊息或日誌裡。

#include "aos/llm/caps.hpp"
#include "aos/llm/message.hpp"
#include "aos/llm/params.hpp"
#include "aos/llm/reply.hpp"
#include "aos/llm/tool.hpp"

#include <asio/awaitable.hpp>

#include <chrono>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace aos::llm {

struct LlmConfig {
    std::string model = "deepseek-chat";

    // base url 或完整的 /chat/completions 都可以，會自己整理。
    std::string url = "http://localhost:4000";

    // 留空就照順序找環境變數 AOS_LLM_KEY、OPENAI_API_KEY，
    // 都沒有就用 "hello" 頂著（本機 proxy 通常不檢查）。
    std::string key;

    Params params;

    // 端點自己報的能力**會說謊**（兩個方向的謊報都遇過），所以留一格覆寫。
    Caps caps_override;

    std::chrono::seconds timeout{120};
};

class Llm {
public:
    explicit Llm(LlmConfig config = {});

    [[nodiscard]] const std::string& model() const { return config_.model; }
    [[nodiscard]] Params& params() { return config_.params; }
    [[nodiscard]] const Params& params() const { return config_.params; }
    void set_model(std::string model) { config_.model = std::move(model); }

    // 問端點這顆模型會什麼。問到的整表記著，之後不再問 ——
    // **問不到的空表也算問過**，所以改完 proxy 設定要 forget_caps()。
    [[nodiscard]] asio::awaitable<Caps> caps();
    void forget_caps() { cached_.reset(); }

    // 端點上有哪些模型。問不到就回空的。
    [[nodiscard]] asio::awaitable<std::vector<std::string>> models();

    // 能力明確不足就回一句話，可以用就回 nullopt。
    // **不知道一律放行** —— 把「不知道」當成「不行」會在本地就把人擋死。
    [[nodiscard]] asio::awaitable<std::optional<std::string>> check(
        bool has_images, bool has_tools, std::string_view tool_choice);

    // 一次呼叫。
    //
    // messages / tools / tool_choice 指到的東西要活到 ask() 回來為止 ——
    // 它們是 span 與 string_view，這裡不複製。
    struct Ask {
        std::span<const Message> messages;
        std::span<const ToolSchema> tools = {};
        std::string_view tool_choice = {};

        // 給了就是串流：每收到一段就叫它一次。沒給就一次收完。
        PartHandler on_part = nullptr;
    };

    // 永遠回一個 Reply，不丟例外。壞掉的話 reply.err 有東西、bool(reply) 是 false。
    [[nodiscard]] asio::awaitable<Reply> ask(Ask request);

private:
    [[nodiscard]] std::vector<std::string> headers() const;
    [[nodiscard]] std::string completions_url() const;

    LlmConfig config_;
    std::string key_;  // 解析過的金鑰。不會被印出去。
    std::optional<Caps> cached_;
};

}  // namespace aos::llm
