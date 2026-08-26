#pragma once

/* 模型能力、token 用量與請求參數。 */

#include <aos/export.h>

#include <cstdint>
#include <optional>
#include <string>

namespace aos::llms {

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

}  // namespace aos::llms
