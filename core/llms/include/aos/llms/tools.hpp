#pragma once

/* tool call 的結構、串流累積器與 ToolSet 驗證合併。 */

#include <aos/export.h>

#include <cstddef>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace aos::llms {

struct RawToolCall {
    std::string id;
    std::string name;
    std::string arguments;
};

struct ToolCall {
    std::string id;
    std::string name;
    /* 合法時保留模型給的 JSON 原字串；不合法時為空。 */
    std::string args;
    /* 只有 args 不合法時有值，讓呼叫端仍看得到模型原文。 */
    std::optional<std::string> args_raw;
};

struct ToolCallDelta {
    std::size_t index = 0;
    std::string id;
    std::string name;
    std::string arguments;
};

class ToolCallAccumulator {
public:
    struct Impl;

    AOS_API ToolCallAccumulator();
    AOS_API ToolCallAccumulator(ToolCallAccumulator &&) noexcept;
    AOS_API ToolCallAccumulator &operator=(ToolCallAccumulator &&) noexcept;
    AOS_API ~ToolCallAccumulator();

    AOS_API void feed(const ToolCallDelta &delta);
    AOS_API bool empty() const noexcept;
    AOS_API std::vector<RawToolCall> raw() const;

private:
    std::unique_ptr<Impl> impl_;
};

AOS_API ToolCall tool_call_entry(const RawToolCall &raw);
AOS_API std::string tool_calls_history_json(
    const std::string &content, const std::vector<RawToolCall> &calls);

using ToolDispatch =
    std::function<std::string(const char *args_json, std::size_t size)>;
using DispatchMap = std::map<std::string, ToolDispatch>;

struct ToolBundle {
    /* OpenAI tools array 的 JSON 字串。 */
    std::string schemas_json;
    DispatchMap dispatch;
};

enum class ToolSetState {
    Ok,
    InvalidArgument,
    JsonSyntax,
    InvalidFormat,
    NameMismatch,
    DuplicateName,
};

AOS_API const char *to_string(ToolSetState state) noexcept;

class ToolSet {
public:
    struct Impl;

    AOS_API ToolSet();
    AOS_API ToolSet(const ToolSet &) noexcept;
    AOS_API ToolSet(ToolSet &&) noexcept;
    AOS_API ToolSet &operator=(const ToolSet &) noexcept;
    AOS_API ToolSet &operator=(ToolSet &&) noexcept;
    AOS_API ~ToolSet();

    AOS_API bool empty() const noexcept;
    AOS_API std::string schemas_json() const;
    AOS_API std::vector<std::string> names() const;
    AOS_API std::string dispatch(const std::string &name,
                                 const char *args_json,
                                 std::size_t size) const;

private:
    std::shared_ptr<const Impl> impl_;

    AOS_API explicit ToolSet(std::shared_ptr<const Impl> impl) noexcept;
    friend struct detail_ToolSetAccess;
};

AOS_API ToolSetState normalize_tools(const std::vector<ToolBundle> &sources,
                                     ToolSet &out, std::string &message);

}  // namespace aos::llms
