// LLM 這一層的離線檢查：request 怎麼組、回應怎麼拆。完全不碰網路。
//
// 這裡驗得到的東西正好是最容易出錯的那些：送出去的形狀不對，或回來的形狀跟
// 想的不一樣。兩件事都不需要連線就能問清楚。
#include "check.hpp"

#include "aos/llm/agentloop.hpp"
#include "aos/llm/caps.hpp"
#include "aos/llm/tool.hpp"
#include "aos/llm/wire.hpp"

#include <nlohmann/json.hpp>

#include <string>
#include <vector>

using nlohmann::json;
using namespace aos::llm;

namespace {

void test_payload_only_sends_what_was_set() {
    const std::vector<Message> messages{
        Message{.role = "user", .content = "你好"},
    };
    Params params;
    params.temperature = 0.5;  // 只設這一個

    const auto payload = build_payload(
        {.model = "m", .messages = messages, .params = &params});
    AOS_CHECK(payload.has_value());

    const json body = json::parse(*payload);
    AOS_CHECK(body["model"] == "m");
    AOS_CHECK(body["stream"] == false);
    AOS_CHECK(body["temperature"] == 0.5);
    // 沒設定的旋鈕一個都不該出現 —— 送一個猜出來的預設值等於替使用者做決定。
    AOS_CHECK(!body.contains("top_p"));
    AOS_CHECK(!body.contains("max_tokens"));
    AOS_CHECK(!body.contains("stop"));
    AOS_CHECK(!body.contains("tools"));
}

void test_extra_cannot_override_the_three_managed_fields() {
    const std::vector<Message> messages{Message{.role = "user", .content = "嗨"}};
    Params params;
    params.extra = R"({"reasoning_effort":"high","stream":true,"model":"別的"})";

    const auto payload = build_payload(
        {.model = "真的那個", .messages = messages, .params = &params});
    AOS_CHECK(payload.has_value());

    const json body = json::parse(*payload);
    AOS_CHECK(body["reasoning_effort"] == "high");  // 非標準的鍵照送
    AOS_CHECK(body["model"] == "真的那個");         // 但這三個蓋不掉
    AOS_CHECK(body["stream"] == false);
}

void test_broken_extra_is_reported_before_sending() {
    const std::vector<Message> messages{Message{.role = "user", .content = "嗨"}};
    Params params;
    params.extra = "{這不是 JSON";

    const auto payload =
        build_payload({.model = "m", .messages = messages, .params = &params});
    AOS_CHECK(!payload.has_value());
}

void test_tool_choice_without_tools_is_an_error() {
    const std::vector<Message> messages{Message{.role = "user", .content = "嗨"}};
    const auto payload = build_payload(
        {.model = "m", .messages = messages, .tool_choice = "required"});
    AOS_CHECK(!payload.has_value());
}

void test_assistant_tool_call_round_trips_into_the_payload() {
    // 帶 tool_calls 的 assistant message 後面一定要接對應的 tool message，
    // 而且形狀要跟端點收的一模一樣，不然下一步會被打回票。
    const std::vector<Message> messages{
        Message{.role = "user", .content = "查天氣"},
        Message{.role = "assistant",
                .content = "",
                .tool_calls = {ToolCall{.id = "call_1",
                                        .name = "weather",
                                        .arguments = R"({"city":"台北"})"}}},
        Message{.role = "tool", .content = "晴", .tool_call_id = "call_1"},
    };

    const auto payload = build_payload({.model = "m", .messages = messages});
    AOS_CHECK(payload.has_value());

    const json body = json::parse(*payload);
    const json& assistant = body["messages"][1];
    // 只叫工具沒說話時 content 要是 null，不是空字串。
    AOS_CHECK(assistant["content"].is_null());
    AOS_CHECK(assistant["tool_calls"][0]["id"] == "call_1");
    AOS_CHECK(assistant["tool_calls"][0]["type"] == "function");
    AOS_CHECK(assistant["tool_calls"][0]["function"]["name"] == "weather");
    AOS_CHECK(body["messages"][2]["tool_call_id"] == "call_1");
}

void test_completion_is_parsed() {
    const auto reply = parse_completion(R"({
        "choices": [{
            "message": {"content": "答案", "reasoning_content": "想了一下"},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 3,
                  "prompt_tokens_details": {"cached_tokens": 8}}
    })");

    AOS_CHECK(static_cast<bool>(reply));
    AOS_CHECK(reply.text == "答案");
    AOS_CHECK(reply.reasoning == "想了一下");
    AOS_CHECK(reply.finish_reason == "stop");
    AOS_CHECK(reply.usage.has_value());
    AOS_CHECK(reply.usage->prompt == 10);
    AOS_CHECK(reply.usage->cached == 8);
    // 缺的欄位是 nullopt 而不是 0 —— 分不開「沒有」和「是零」就沒辦法驗快取。
    AOS_CHECK(!reply.usage->total.has_value());
    AOS_CHECK(!reply.usage->reasoning.has_value());
}

void test_endpoint_error_becomes_reply_err() {
    const auto reply =
        parse_completion(R"({"error": {"message": "沒有這顆模型"}})");
    AOS_CHECK(!static_cast<bool>(reply));
    AOS_CHECK(reply.err == "沒有這顆模型");
}

void test_garbage_response_does_not_look_like_success() {
    const auto reply = parse_completion("<html>502 Bad Gateway</html>");
    AOS_CHECK(!static_cast<bool>(reply));
    AOS_CHECK(reply.text.empty());
}

void test_stream_survives_a_chunk_split_mid_line() {
    StreamAccumulator accumulator;

    // 一段 TCP 資料常常切在半行中間。這裡故意把 "data:" 那行切成兩半，
    // 而且切在多位元組字元的中間也不影響 —— 這一層只認換行。
    auto parts = accumulator.feed("data: {\"choices\":[{\"delta\":{\"cont");
    AOS_CHECK(parts.empty());  // 還沒湊成一整行，不該吐出任何東西

    parts = accumulator.feed("ent\":\"你\"}}]}\n");
    AOS_CHECK(parts.size() == 1);
    AOS_CHECK(parts[0].kind == PartKind::answer);
    AOS_CHECK(parts[0].text == "你");

    parts = accumulator.feed(
        "data: {\"choices\":[{\"delta\":{\"content\":\"好\"},"
        "\"finish_reason\":\"stop\"}]}\n"
        "data: {\"usage\":{\"total_tokens\":7}}\n"
        "data: [DONE]\n");
    AOS_CHECK(parts.size() == 1);
    AOS_CHECK(parts[0].text == "好");

    const auto reply = accumulator.finish();
    AOS_CHECK(static_cast<bool>(reply));
    AOS_CHECK(reply.text == "你好");
    AOS_CHECK(reply.finish_reason == "stop");
    AOS_CHECK(reply.usage.has_value() && reply.usage->total == 7);
}

void test_stream_separates_thinking_from_the_answer() {
    StreamAccumulator accumulator;
    const auto parts = accumulator.feed(
        "data: {\"choices\":[{\"delta\":"
        "{\"reasoning_content\":\"嗯\",\"content\":\"答\"}}]}\n");

    // 兩種字分開給。混在一起的話，把收到的字直接印給使用者看，
    // 等於把模型的內心戲印到人臉上。
    AOS_CHECK(parts.size() == 2);
    AOS_CHECK(parts[0].kind == PartKind::think && parts[0].text == "嗯");
    AOS_CHECK(parts[1].kind == PartKind::answer && parts[1].text == "答");
}

void test_stream_reassembles_tool_call_fragments() {
    StreamAccumulator accumulator;
    // id 和 name 只在第一片出現，arguments 是一小段一小段接起來的。
    (void)accumulator.feed(
        "data: {\"choices\":[{\"delta\":{\"tool_calls\":[{\"index\":0,"
        "\"id\":\"call_1\",\"function\":{\"name\":\"w\",\"arguments\":\"{\\\"c\"}}]}}]}\n");
    (void)accumulator.feed(
        "data: {\"choices\":[{\"delta\":{\"tool_calls\":[{\"index\":0,"
        "\"function\":{\"arguments\":\"\\\":1}\"}}]}}]}\n");
    (void)accumulator.feed("data: [DONE]\n");

    const auto reply = accumulator.finish();
    AOS_CHECK(reply.calls.size() == 1);
    AOS_CHECK(reply.calls[0].id == "call_1");
    AOS_CHECK(reply.calls[0].name == "w");
    AOS_CHECK(reply.calls[0].arguments == R"({"c":1})");
}

void test_stream_that_never_started_is_an_error_not_silence() {
    StreamAccumulator accumulator;
    const auto reply = accumulator.finish();
    // 「模型沒話說」和「還沒開口就斷線」必須分得開。
    AOS_CHECK(!static_cast<bool>(reply));
    AOS_CHECK(!reply.spoke());
}

void test_caps_typo_is_an_error_not_a_shrug() {
    const Caps caps{.tools = true};
    AOS_CHECK(caps.get("tools").value() == true);
    AOS_CHECK(!caps.get("vision").value().has_value());  // 沒說 = 不知道
    // 名字打錯不會安靜地變成「不知道」，那是最難查的那種錯。
    AOS_CHECK(!caps.get("toolz").has_value());
    AOS_CHECK(Caps::names().size() == 7);
}

void test_caps_overlay_keeps_remote_where_override_is_silent() {
    const Caps remote{.tools = true, .vision = false};
    const Caps override_{.vision = true};
    const Caps merged = Caps::overlay(remote, override_);

    AOS_CHECK(merged.tools == true);   // 覆寫沒說話，沿用遠端
    AOS_CHECK(merged.vision == true);  // 覆寫說了，蓋掉遠端的謊
}

void test_model_info_missing_field_means_unknown() {
    const auto table = parse_model_info(R"({"data": [
        {"model_name": "a", "model_info": {"supports_vision": true}},
        {"model_name": "b", "model_info": {}}
    ]})");

    AOS_CHECK(table.size() == 2);
    AOS_CHECK(table[0].second.vision == true);
    AOS_CHECK(!table[0].second.tools.has_value());  // 沒提到 = 不知道，不是 false
    AOS_CHECK(!table[1].second.vision.has_value());
}

void test_url_shapes() {
    AOS_CHECK(normalize_base_url("http://x:4000/v1/chat/completions") ==
              "http://x:4000/v1");
    AOS_CHECK(normalize_base_url("http://x:4000/") == "http://x:4000");
    AOS_CHECK(root_url("http://x:4000/v1/chat/completions") == "http://x:4000");
}

void test_tool_builder_emits_a_valid_schema() {
    const auto schema = ToolBuilder{"shout"}
                            .describe("把字\"變\"大聲")
                            .text_parameter("text", "要喊的字", true)
                            .integer_parameter("times", "重複幾次")
                            .build();

    AOS_CHECK(schema.name == "shout");
    const json parsed = json::parse(schema.json);
    AOS_CHECK(parsed["type"] == "function");
    AOS_CHECK(parsed["function"]["name"] == "shout");
    // 描述裡的引號要逃脫得掉，不然整段 JSON 就壞了。
    AOS_CHECK(parsed["function"]["description"] == "把字\"變\"大聲");
    AOS_CHECK(parsed["function"]["parameters"]["properties"]["times"]["type"] ==
              "integer");
    AOS_CHECK(parsed["function"]["parameters"]["required"].size() == 1);
    AOS_CHECK(parsed["function"]["parameters"]["required"][0] == "text");
}

void test_merge_tools_refuses_a_schema_with_no_one_to_answer_it() {
    ToolSet lonely;
    lonely.schemas.push_back(ToolSchema{.name = "a", .json = "{}"});
    // 有 schema 沒 dispatch：模型叫得動，但沒人接。
    AOS_CHECK(!merge_tools({lonely}).has_value());

    ToolSet good;
    good.schemas.push_back(ToolSchema{.name = "a", .json = "{}"});
    good.dispatch.emplace("a", [](std::string_view) { return std::string{"ok"}; });
    AOS_CHECK(merge_tools({good}).has_value());

    // 撞名是錯，不是先到先贏 —— 安靜挑一個只會讓人找不到另一個。
    AOS_CHECK(!merge_tools({good, good}).has_value());
}

}  // namespace

int main() {
    test_payload_only_sends_what_was_set();
    test_extra_cannot_override_the_three_managed_fields();
    test_broken_extra_is_reported_before_sending();
    test_tool_choice_without_tools_is_an_error();
    test_assistant_tool_call_round_trips_into_the_payload();
    test_completion_is_parsed();
    test_endpoint_error_becomes_reply_err();
    test_garbage_response_does_not_look_like_success();
    test_stream_survives_a_chunk_split_mid_line();
    test_stream_separates_thinking_from_the_answer();
    test_stream_reassembles_tool_call_fragments();
    test_stream_that_never_started_is_an_error_not_silence();
    test_caps_typo_is_an_error_not_a_shrug();
    test_caps_overlay_keeps_remote_where_override_is_silent();
    test_model_info_missing_field_means_unknown();
    test_url_shapes();
    test_tool_builder_emits_a_valid_schema();
    test_merge_tools_refuses_a_schema_with_no_one_to_answer_it();
    return aos::testing::report();
}
