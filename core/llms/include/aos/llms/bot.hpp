#pragma once

/* 一次 ask 的請求、串流 sink、Reply 與持有 history 的 Bot。 */

#include <aos/export.h>

#include <aos/llms/caps.hpp>
#include <aos/llms/llm.hpp>
#include <aos/llms/tools.hpp>
#include <aos/llms/transport.hpp>

#include <cstddef>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::llms {

struct Ask {
    std::optional<std::string> prompt;
    std::vector<std::string> images;
    /* {call_id: "工具輸出"}；沒給就不新增 tool message。 */
    std::optional<std::string> tool_results_json;
    bool remember = true;
    bool stream = false;
    /* JSON 字串，例如 \"required\" 或指定 function 的 object。 */
    std::optional<std::string> tool_choice_json;
};

enum class ReplyPart {
    Think,
    Answer,
};

AOS_API const char *to_string(ReplyPart part) noexcept;
using ReplySink = std::function<void(std::string_view)>;
using ReplyPartSink = std::function<void(ReplyPart, std::string_view)>;

class Reply {
public:
    struct Impl;

    std::string text;
    std::vector<ToolCall> calls;
    std::optional<std::string> reasoning;
    std::optional<std::string> finish_reason;
    std::optional<Usage> usage;
    std::optional<ReplyError> err;
    std::size_t checkpoint = 0;

    AOS_API Reply();
    AOS_API Reply(Reply &&) noexcept;
    AOS_API Reply &operator=(Reply &&) noexcept;
    AOS_API ~Reply();

    AOS_API explicit operator bool() const noexcept;
    /* 串流開始前設定；一般 sink 只收到答案，不會混入思考。 */
    AOS_API void set_sink(ReplySink sink);
    /* 同時接收思考與答案；種類由 ReplyPart 區分。 */
    AOS_API void set_part_sink(ReplyPartSink sink);
    /* 串流會收到完為止再回；非串流維持原本行為。 */
    AOS_API const std::string &all_text();
    /* 寫回 history 與關閉 transport 的唯一收尾點；可重複呼叫。 */
    AOS_API void finish();

private:
    std::unique_ptr<Impl> impl_;
    friend struct detail_ReplyAccess;
};

class Bot {
public:
    struct Impl;

    AOS_API explicit Bot(LLM llm = LLM(),
                         std::optional<std::string> system = std::nullopt,
                         ToolSet tools = ToolSet());
    AOS_API Bot(Bot &&) noexcept;
    AOS_API Bot &operator=(Bot &&) noexcept;
    AOS_API ~Bot();

    AOS_API LLM &llm() noexcept;
    AOS_API const LLM &llm() const noexcept;
    AOS_API void set_llm(LLM llm);
    AOS_API std::optional<std::string> system() const;
    AOS_API void set_system(std::optional<std::string> system);
    AOS_API void reset();
    AOS_API std::string history_json() const;
    AOS_API std::vector<ToolCall> pending_calls() const;
    AOS_API Reply ask(const Ask &request);
    AOS_API Reply ask(const std::string &prompt);

private:
    std::shared_ptr<Impl> impl_;
};

}  // namespace aos::llms
