#pragma once

#include <aos/export.h>

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::llm {

struct Message {
    std::string role;
    std::string content;
};

struct Options {
    std::string url = "http://localhost:1234/v1";
    std::string model = "qwen/qwen3.5-9b";
    std::string key;
    long timeout_ms = 120000;
};

struct CommandOptions {
    Options completion;
    std::optional<std::string> system;
    std::optional<std::string> messages_file;
    std::string engine = "lmstudio";
    int priority = 0;
    bool slots = false;
};

AOS_API Options options_from_env();

AOS_API CommandOptions parse_arguments(
    const std::vector<std::string> &arguments);

AOS_API std::vector<Message> parse_messages_json(std::string_view text);

AOS_API std::string make_request_json(const std::vector<Message> &messages,
                                      const Options &options);

AOS_API std::string parse_response_text(std::string_view text);

/* 回應 JSON 的 model 欄；沒有這個欄位就回空字串。 */
AOS_API std::string parse_response_model(std::string_view text);

AOS_API std::string complete(const std::vector<Message> &messages,
                             const Options &options,
                             std::string *served_model = nullptr);

}  // namespace aos::llm
