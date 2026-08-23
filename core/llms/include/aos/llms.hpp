#pragma once

#include <aos/export.h>

#include <cstddef>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace aos::llms {

enum class ErrorKind {
    None,
    InvalidArgument,
    Capability,
    Transport,
    Http,
    Json,
    Response,
    Io,
};

AOS_API const char *to_string(ErrorKind kind) noexcept;

struct ReplyError {
    ErrorKind kind = ErrorKind::None;
    std::string message;
};

struct HttpRequest {
    std::string method = "POST";
    std::string url;
    std::string body;
    std::vector<std::string> headers;
    long timeout_ms = 60000;
};

struct HttpResponse {
    long status = 0;
    std::string body;
    std::string error;
};

using Transport = std::function<HttpResponse(const HttpRequest &)>;

enum class Capability {
    Tools,
    ToolChoice,
    ParallelTools,
    Vision,
    Reasoning,
    JsonSchema,
    Caching,
};

AOS_API const char *to_string(Capability capability) noexcept;

struct Caps {
    std::optional<bool> tools;
    std::optional<bool> tool_choice;
    std::optional<bool> parallel_tools;
    std::optional<bool> vision;
    std::optional<bool> reasoning;
    std::optional<bool> json_schema;
    std::optional<bool> caching;

    AOS_API std::optional<bool> get(Capability capability) const noexcept;
};

struct Usage {
    std::optional<std::int64_t> prompt;
    std::optional<std::int64_t> completion;
    std::optional<std::int64_t> total;
    std::optional<std::int64_t> cached;
    std::optional<std::int64_t> reasoning;
};

struct Params {
    std::optional<double> temperature;
    std::optional<double> top_p;
    std::optional<std::int64_t> max_tokens;
    std::optional<std::int64_t> seed;
    /* JSON 字串或字串陣列；未設定時不送。 */
    std::optional<std::string> stop_json;
    std::optional<double> presence_penalty;
    std::optional<double> frequency_penalty;
    /* JSON object；直接展開，只有 model／messages／stream 會在送出前固定。 */
    std::string extra_json = "{}";

    AOS_API std::string to_json() const;
};

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

struct ModelInfo {
    std::string name;
    Caps caps;
};

class LLM {
public:
    struct Impl;

    AOS_API explicit LLM(std::string model = "deepseek-chat",
                         std::string url = "http://localhost:4000",
                         std::optional<std::string> key = std::nullopt,
                         Params params = {}, long timeout_ms = 60000,
                         Caps caps_override = {}, Transport transport = {});
    AOS_API LLM(const LLM &) noexcept;
    AOS_API LLM(LLM &&) noexcept;
    AOS_API LLM &operator=(const LLM &) noexcept;
    AOS_API LLM &operator=(LLM &&) noexcept;
    AOS_API ~LLM();

    AOS_API std::string model() const;
    AOS_API void set_model(std::string model);
    AOS_API Params params() const;
    AOS_API void set_params(Params params);
    AOS_API std::string base_url() const;
    AOS_API std::string root_url() const;
    AOS_API std::string key() const;

    AOS_API Caps caps() const;
    AOS_API std::optional<bool> supports(Capability capability) const;
    AOS_API std::vector<ModelInfo> models() const;
    AOS_API std::optional<ReplyError> check(bool has_images, bool has_tools,
                                            bool has_tool_choice) const;

    AOS_API static void clear_caps_cache();

private:
    std::shared_ptr<Impl> impl_;
    friend struct detail_LLMAccess;
};

struct Ask {
    std::optional<std::string> prompt;
    std::vector<std::string> images;
    /* {call_id: "工具輸出"}；沒給就不新增 tool message。 */
    std::optional<std::string> tool_results_json;
    bool remember = true;
    /* JSON 字串，例如 \"required\" 或指定 function 的 object。 */
    std::optional<std::string> tool_choice_json;
};

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
    /* S3 會一次拿完；S4 接上 drain 後，這個介面仍可原樣使用。 */
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

enum class PresetState {
    Ok,
    InvalidArgument,
    IoError,
    JsonSyntax,
    InvalidFormat,
    UnknownPreset,
};

AOS_API const char *to_string(PresetState state) noexcept;
AOS_API PresetState load_preset(const std::string &id, LLM &out,
                                std::string &message);
AOS_API PresetState load_preset(const std::string &id, const char *path,
                                LLM &out, std::string &message);
AOS_API std::vector<std::string> preset_ids();

AOS_API std::string normalize_base_url(const std::string &url);
AOS_API std::string endpoint_root_url(const std::string &url);
AOS_API std::string resolve_key(
    const std::optional<std::string> &key = std::nullopt);
AOS_API std::string encode_image_url(const std::string &path_or_url);
AOS_API std::string build_content_json(
    const std::optional<std::string> &prompt,
    const std::vector<std::string> &images);

}  // namespace aos::llms
