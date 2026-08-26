// 同一份 SSE 位元組流在任意 transport 切割下的等價性：整包／不規則／逐 byte 切出來的答案、思考、tool call、history 與請求 body 必須完全一致。

#include <aos/llms.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

std::string complete_stream() {
    return R"(data: {"choices":[{"finish_reason":null,"delta":{"reasoning_content":"想","content":null,"tool_calls":[{"index":0,"id":"call-a","function":{"arguments":"{\"a\":"}}]}}]}

data: {"choices":[{"finish_reason":null,"delta":{"reasoning":"法","content":"答","tool_calls":[{"index":1,"id":"call-b","function":{"arguments":"{\"b\":"}}]}}]}

data: {"choices":[{"finish_reason":"tool_calls","delta":{"tool_calls":[{"index":1,"function":{"name":"second","arguments":"2}"}},{"index":0,"function":{"name":"first","arguments":"1}"}}]}}]}

data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":7,"total_tokens":12,"prompt_tokens_details":{"cached_tokens":2},"completion_tokens_details":{"reasoning_tokens":3}}}

data: [DONE]

data: {broken

)";
}

struct StreamResult {
    std::string text;
    std::string reasoning;
    std::string answers;
    std::string parts;
    std::string calls;
    std::string history;
    std::string request_body;
};

StreamResult run_split(const std::vector<std::size_t> &sizes) {
    const std::string bytes = complete_stream();
    std::size_t stream_calls = 0;
    aos::llms::HttpRequest observed;
    aos::llms::StreamTransport stream =
        [&](const aos::llms::HttpRequest &request,
            const aos::llms::StreamByteSink &sink) {
            ++stream_calls;
            observed = request;
            std::size_t offset = 0;
            for (const std::size_t size : sizes) {
                if (offset == bytes.size()) break;
                const std::size_t take = std::min(size, bytes.size() - offset);
                sink(std::string_view(bytes).substr(offset, take));
                offset += take;
            }
            if (offset < bytes.size()) {
                sink(std::string_view(bytes).substr(offset));
            }
            return aos::llms::HttpResponse{.status = 200};
        };
    aos::llms::Params params;
    params.extra_json =
        R"({"stream":false,"stream_options":{"include_usage":false}})";
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://x", "k", params, 60000, {}, {}, std::move(stream)));
    aos::llms::Ask ask;
    ask.prompt = "問題";
    ask.stream = true;
    aos::llms::Reply reply = bot.ask(ask);
    REQUIRE(stream_calls == 0);
    CHECK(LlmsJson::parse(bot.history_json()).size() == 1);

    std::string answers;
    std::string parts;
    reply.set_sink([&](std::string_view value) { answers += value; });
    reply.set_part_sink([&](aos::llms::ReplyPart part, std::string_view value) {
        parts += aos::llms::to_string(part);
        parts += ':';
        parts += value;
        parts += ';';
    });
    const std::string text = reply.all_text();
    REQUIRE(reply);
    REQUIRE(stream_calls == 1);
    REQUIRE(reply.reasoning.has_value());
    REQUIRE(reply.calls.size() == 2);
    REQUIRE(reply.usage.has_value());
    CHECK(reply.finish_reason == std::optional<std::string>("tool_calls"));
    CHECK(reply.calls[0].id == "call-a");
    CHECK(reply.calls[0].name == "first");
    CHECK(reply.calls[0].args == R"({"a":1})");
    CHECK(reply.calls[1].id == "call-b");
    CHECK(reply.calls[1].name == "second");
    CHECK(reply.calls[1].args == R"({"b":2})");
    CHECK(reply.usage->prompt == 5);
    CHECK(reply.usage->completion == 7);
    CHECK(reply.usage->total == 12);
    CHECK(reply.usage->cached == 2);
    CHECK(reply.usage->reasoning == 3);

    const LlmsJson history = LlmsJson::parse(bot.history_json());
    REQUIRE(history.size() == 2);
    CHECK(history[1]["content"] == "答");
    CHECK(history[1]["tool_calls"][0]["id"] == "call-a");
    CHECK(history[1]["tool_calls"][1]["id"] == "call-b");

    const LlmsJson body = LlmsJson::parse(observed.body);
    CHECK(body["stream"] == true);
    CHECK(body["stream_options"]["include_usage"] == true);
    return {
        .text = text,
        .reasoning = *reply.reasoning,
        .answers = answers,
        .parts = parts,
        .calls = LlmsJson::array({{{"id", reply.calls[0].id},
                                   {"name", reply.calls[0].name},
                                   {"args", reply.calls[0].args}},
                                  {{"id", reply.calls[1].id},
                                   {"name", reply.calls[1].name},
                                   {"args", reply.calls[1].args}}})
                     .dump(),
        .history = history.dump(),
        .request_body = body.dump(),
    };
}

} // namespace

TEST_CASE("SSE parsing is invariant under arbitrary transport splits") {
    const StreamResult whole = run_split({1000000});
    const StreamResult uneven = run_split({1, 2, 7, 3, 19, 1, 41, 5, 2});
    std::vector<std::size_t> bytewise(complete_stream().size(), 1);
    const StreamResult bytes = run_split(bytewise);

    CHECK(whole.text == "答");
    CHECK(whole.reasoning == "想法");
    CHECK(whole.answers == "答");
    CHECK(whole.parts == "think:想;think:法;answer:答;");
    CHECK(uneven.text == whole.text);
    CHECK(uneven.reasoning == whole.reasoning);
    CHECK(uneven.answers == whole.answers);
    CHECK(uneven.parts == whole.parts);
    CHECK(uneven.calls == whole.calls);
    CHECK(uneven.history == whole.history);
    CHECK(uneven.request_body == whole.request_body);
    CHECK(bytes.text == whole.text);
    CHECK(bytes.reasoning == whole.reasoning);
    CHECK(bytes.calls == whole.calls);
    CHECK(bytes.history == whole.history);
}
