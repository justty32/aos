#include <aos/llms.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <string>

namespace {

aos::llms::ToolDispatch echo_dispatch() {
    return [](const char *data, std::size_t size) {
        return std::string(data, size);
    };
}

std::string schema(const std::string &name) {
    return "[{\"type\":\"function\",\"function\":{\"name\":\"" +
        name + "\"}}]";
}

}  // namespace

TEST_CASE("tool schemas and dispatch names must match exactly") {
    aos::llms::ToolSet tools;
    std::string message;
    CHECK(aos::llms::normalize_tools(
              {{.schemas_json = schema("one"),
                .dispatch = {{"two", echo_dispatch()}}}},
              tools, message) == aos::llms::ToolSetState::NameMismatch);

    REQUIRE(aos::llms::normalize_tools(
                {{.schemas_json = schema("one"),
                  .dispatch = {{"one", echo_dispatch()}}}},
                tools, message) == aos::llms::ToolSetState::Ok);
    CHECK(tools.names() == std::vector<std::string>{"one"});
    CHECK(tools.dispatch("one", "{}", 2) == "{}");
}

TEST_CASE("tool normalization rejects names colliding within or across sources") {
    aos::llms::ToolSet tools;
    std::string message;
    const std::string duplicate =
        "[" + schema("same").substr(1, schema("same").size() - 2) + "," +
        schema("same").substr(1, schema("same").size() - 2) + "]";
    CHECK(aos::llms::normalize_tools(
              {{.schemas_json = duplicate,
                .dispatch = {{"same", echo_dispatch()}}}},
              tools, message) == aos::llms::ToolSetState::DuplicateName);

    CHECK(aos::llms::normalize_tools(
              {{.schemas_json = schema("same"),
                .dispatch = {{"same", echo_dispatch()}}},
               {.schemas_json = schema("same"),
                .dispatch = {{"same", echo_dispatch()}}}},
              tools, message) == aos::llms::ToolSetState::DuplicateName);
}

TEST_CASE("embedded presets create LLMs without duplicating capabilities") {
    aos::llms::LLM llm;
    std::string message;
    REQUIRE(aos::llms::load_preset("deepseek-chat", llm, message) ==
            aos::llms::PresetState::Ok);
    CHECK(llm.model() == "deepseek-chat");
    CHECK(llm.base_url() == "http://localhost:4000");
    const LlmsJson params = LlmsJson::parse(llm.params().to_json());
    CHECK(params["temperature"] == 1.3);
    CHECK(params["max_tokens"] == 384000);
    const auto ids = aos::llms::preset_ids();
    CHECK(std::find(ids.begin(), ids.end(), "lm-qwen3.5-9b") != ids.end());
}

TEST_CASE("presets reject both missing and unknown keys") {
    aos::llms::LLM llm;
    std::string message;
    TempFile missing(
        ".json",
        R"({"x":{"endpoint":"http://x","model":"m"}})");
    CHECK(aos::llms::load_preset("x", missing.path.c_str(), llm, message) ==
          aos::llms::PresetState::InvalidFormat);

    TempFile extra(
        ".json",
        R"({"x":{"endpoint":"http://x","model":"m","parameters":{},"caps":{}}})");
    CHECK(aos::llms::load_preset("x", extra.path.c_str(), llm, message) ==
          aos::llms::PresetState::InvalidFormat);
}
