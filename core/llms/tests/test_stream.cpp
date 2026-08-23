#include <aos/llms.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

std::string sse(const LlmsJson &value) {
    return "data: " + value.dump() + "\n\n";
}

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

aos::llms::Reply streamed_reply(aos::llms::Bot &bot,
                                aos::llms::StreamTransport stream) {
    bot.set_llm(aos::llms::LLM("m", "http://x", "k", {}, 60000, {}, {},
                               std::move(stream)));
    aos::llms::Ask ask;
    ask.prompt = "問題";
    ask.stream = true;
    return bot.ask(ask);
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

TEST_CASE("stream chunks use defensive fields and accept usage-only chunks") {
    std::string bytes;
    bytes += sse({{"usage", {{"prompt_tokens", 9}}}});
    bytes += sse({{"choices", nullptr}});
    bytes += sse({{"choices", LlmsJson::array()}});
    bytes += sse({{"choices", LlmsJson::array({nullptr})}});
    bytes += sse({{"choices", {{{"finish_reason", 7}, {"delta", nullptr}}}}});
    bytes += sse(
        {{"choices", {{{"delta", {{"content", 7}, {"tool_calls", "bad"}}}}}}});
    bytes +=
        sse({{"choices",
              {{{"finish_reason", "stop"}, {"delta", LlmsJson::object()}}}}});
    bytes += "data: [DONE]\n\n";

    aos::llms::Bot bot;
    aos::llms::Reply reply =
        streamed_reply(bot, [bytes](const auto &, const auto &sink) {
            sink(bytes);
            return aos::llms::HttpResponse{.status = 200};
        });
    CHECK(reply.all_text().empty());
    REQUIRE(reply);
    CHECK(reply.finish_reason == std::optional<std::string>("stop"));
    REQUIRE(reply.usage.has_value());
    CHECK(reply.usage->prompt == 9);
    const LlmsJson history = LlmsJson::parse(bot.history_json());
    REQUIRE(history.size() == 2);
    CHECK(history[1]["content"] == "");
}

TEST_CASE("stream failures after ask stay in Reply and follow finish rules") {
    SECTION("zero-byte disconnect rolls the whole turn back") {
        aos::llms::Bot bot;
        aos::llms::Reply reply =
            streamed_reply(bot, [](const auto &, const auto &) {
                return aos::llms::HttpResponse{.status = 200};
            });
        CHECK(reply.all_text().empty());
        REQUIRE(reply);
        CHECK_FALSE(reply.finish_reason.has_value());
        CHECK(bot.history_json() == "[]");
    }
    SECTION("malformed event rolls an untouched turn back") {
        aos::llms::Bot bot;
        aos::llms::Reply reply =
            streamed_reply(bot, [](const auto &, const auto &sink) {
                sink("data: {broken\n\n");
                return aos::llms::HttpResponse{.status = 200};
            });
        CHECK(bot.history_json() != "[]");
        CHECK_NOTHROW(reply.all_text());
        CHECK_FALSE(reply);
        CHECK(reply.err->kind == aos::llms::ErrorKind::Json);
        CHECK(bot.history_json() == "[]");
    }
    SECTION("transport throw is caught after ask returns") {
        aos::llms::Bot bot;
        aos::llms::Reply reply = streamed_reply(
            bot, [](const auto &, const auto &) -> aos::llms::HttpResponse {
                throw std::runtime_error("offline");
            });
        CHECK_NOTHROW(reply.all_text());
        CHECK_FALSE(reply);
        CHECK(reply.err->kind == aos::llms::ErrorKind::Transport);
        CHECK(bot.history_json() == "[]");
    }
    SECTION("partial answer stays in history when transport later fails") {
        aos::llms::Bot bot;
        aos::llms::Reply reply =
            streamed_reply(bot, [](const auto &, const auto &sink) {
                sink(sse({{"choices",
                           {{{"finish_reason", nullptr},
                             {"delta", {{"content", "半"}}}}}}}));
                return aos::llms::HttpResponse{.error = "斷線"};
            });
        CHECK(reply.all_text() == "半");
        CHECK_FALSE(reply);
        const LlmsJson history = LlmsJson::parse(bot.history_json());
        REQUIRE(history.size() == 2);
        CHECK(history[1]["content"] == "半");
    }
    SECTION("answer sink failures do not escape") {
        aos::llms::Bot bot;
        aos::llms::Reply reply =
            streamed_reply(bot, [](const auto &, const auto &sink) {
                sink(sse({{"choices", {{{"delta", {{"content", "字"}}}}}}}));
                return aos::llms::HttpResponse{.status = 200};
            });
        reply.set_sink(
            [](std::string_view) { throw std::runtime_error("sink failed"); });
        CHECK_NOTHROW(reply.all_text());
        CHECK_FALSE(reply);
        CHECK(reply.err->kind == aos::llms::ErrorKind::Response);
        CHECK(reply.text == "字");
    }
}

TEST_CASE("Reply destructor and early finish deterministically roll back") {
    int stream_calls = 0;
    aos::llms::Bot bot;
    {
        aos::llms::Reply reply =
            streamed_reply(bot, [&](const auto &, const auto &) {
                ++stream_calls;
                return aos::llms::HttpResponse{.status = 200};
            });
        REQUIRE(LlmsJson::parse(bot.history_json()).size() == 1);
    }
    CHECK(stream_calls == 0);
    CHECK(bot.history_json() == "[]");

    aos::llms::Reply reply =
        streamed_reply(bot, [&](const auto &, const auto &) {
            ++stream_calls;
            return aos::llms::HttpResponse{.status = 200};
        });
    reply.finish();
    reply.finish();
    CHECK(stream_calls == 0);
    CHECK(bot.history_json() == "[]");
}

TEST_CASE("streamed tool-only history keeps null content") {
    aos::llms::Bot bot;
    aos::llms::Reply reply = streamed_reply(
        bot, [](const auto &, const auto &sink) {
            sink("data: {\"choices\":[{\"finish_reason\":\"tool_calls\","
                 "\"delta\":{\"tool_calls\":[{\"index\":0,\"id\":\"call\","
                 "\"function\":{\"name\":\"lookup\",\"arguments\":\"{}\"}}]}}]}\n\n"
                 "data: [DONE]\n\n");
            return aos::llms::HttpResponse{.status = 200};
        });
    reply.all_text();
    REQUIRE(reply);
    REQUIRE(reply.calls.size() == 1);
    const LlmsJson history = LlmsJson::parse(bot.history_json());
    REQUIRE(history.size() == 2);
    CHECK(history[1]["content"].is_null());
    CHECK(history[1]["tool_calls"][0]["function"]["arguments"] == "{}");
}
