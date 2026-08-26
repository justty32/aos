// 串流 Reply 的行為：防禦性欄位與 usage-only 片段、零位元組斷線／壞事件／transport 例外／sink 例外的收斂與 history 進退、解構與提前 finish、tool-only 的 null content。

#include <aos/llms.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

namespace {

std::string sse(const LlmsJson &value) {
    return "data: " + value.dump() + "\n\n";
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
