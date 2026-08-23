#include <aos/llms.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

TEST_CASE("tool call accumulator joins interleaved fragments by index") {
    aos::llms::ToolCallAccumulator accumulator;
    accumulator.feed({.index = 1, .id = "call-b", .name = "second",
                      .arguments = "{\"b\":"});
    accumulator.feed({.index = 0, .id = "call-a", .name = "first",
                      .arguments = "{\"a\":"});
    accumulator.feed({.index = 1, .arguments = "2}"});
    accumulator.feed({.index = 0, .arguments = "1}"});

    const std::vector<aos::llms::RawToolCall> raw = accumulator.raw();
    REQUIRE(raw.size() == 2);
    CHECK(raw[0].id == "call-a");
    CHECK(raw[0].name == "first");
    CHECK(raw[0].arguments == R"({"a":1})");
    CHECK(raw[1].id == "call-b");
    CHECK(raw[1].arguments == R"({"b":2})");
}

TEST_CASE("invalid tool arguments preserve raw text without throwing") {
    const aos::llms::ToolCall call = aos::llms::tool_call_entry(
        {.id = "x", .name = "broken", .arguments = "{not-json"});
    CHECK(call.args.empty());
    REQUIRE(call.args_raw.has_value());
    CHECK(*call.args_raw == "{not-json");
}

TEST_CASE("tool call history uses API shape and null content") {
    const std::vector<aos::llms::RawToolCall> calls = {
        {.id = "x", .name = "lookup", .arguments = R"({"q":"a"})"}};
    const LlmsJson only_call = LlmsJson::parse(
        aos::llms::tool_calls_history_json("", calls));
    CHECK(only_call["role"] == "assistant");
    CHECK(only_call["content"].is_null());
    CHECK(only_call["tool_calls"][0]["id"] == "x");
    CHECK(only_call["tool_calls"][0]["type"] == "function");
    CHECK(only_call["tool_calls"][0]["function"]["name"] == "lookup");
    CHECK(only_call["tool_calls"][0]["function"]["arguments"] ==
          R"({"q":"a"})");

    const LlmsJson with_text = LlmsJson::parse(
        aos::llms::tool_calls_history_json("我來查", calls));
    CHECK(with_text["content"] == "我來查");
}
