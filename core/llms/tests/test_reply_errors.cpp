// Bot::ask 的錯誤契約與 history rollback：transport／HTTP／JSON／回應形狀、per-turn checkpoint、送出前後的 user message、tool_choice 缺 tools、落空的一輪與 remember false。

#include <aos/llms.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <stdexcept>
#include <string>

TEST_CASE("ask turns transport HTTP JSON and response failures into Reply errors") {
    SECTION("transport") {
        aos::llms::Bot bot(aos::llms::LLM(
            "m", "http://x", "k", {}, 60000, {},
            [](const auto &) {
                return aos::llms::HttpResponse{.error = "offline"};
            }));
        aos::llms::Reply reply = bot.ask("問題");
        CHECK_FALSE(reply);
        CHECK(reply.err->kind == aos::llms::ErrorKind::Transport);
        CHECK(bot.history_json() == "[]");
    }
    SECTION("HTTP") {
        aos::llms::Bot bot(aos::llms::LLM(
            "m", "http://x", "k", {}, 60000, {},
            [](const auto &) {
                return aos::llms::HttpResponse{.status = 503,
                                               .body = "busy"};
            }));
        aos::llms::Reply reply = bot.ask("問題");
        CHECK_FALSE(reply);
        CHECK(reply.err->kind == aos::llms::ErrorKind::Http);
        CHECK(bot.history_json() == "[]");
    }
    SECTION("bad JSON") {
        aos::llms::Bot bot(aos::llms::LLM(
            "m", "http://x", "k", {}, 60000, {},
            [](const auto &) {
                return aos::llms::HttpResponse{.status = 200,
                                               .body = "not-json"};
            }));
        aos::llms::Reply reply = bot.ask("問題");
        CHECK_FALSE(reply);
        CHECK(reply.err->kind == aos::llms::ErrorKind::Json);
        CHECK(bot.history_json() == "[]");
    }
    SECTION("bad shape") {
        aos::llms::Bot bot(aos::llms::LLM(
            "m", "http://x", "k", {}, 60000, {},
            [](const auto &) {
                return aos::llms::HttpResponse{.status = 200,
                                               .body = R"({"choices":[]})"};
            }));
        aos::llms::Reply reply = bot.ask("問題");
        CHECK_FALSE(reply);
        CHECK(reply.err->kind == aos::llms::ErrorKind::Response);
        CHECK(bot.history_json() == "[]");
    }
    SECTION("throwing transport") {
        aos::llms::Bot bot(aos::llms::LLM(
            "m", "http://x", "k", {}, 60000, {},
            [](const auto &) -> aos::llms::HttpResponse {
                throw std::runtime_error("boom");
            }));
        aos::llms::Reply reply = bot.ask("問題");
        CHECK_FALSE(reply);
        CHECK(reply.err->kind == aos::llms::ErrorKind::Transport);
        CHECK(bot.history_json() == "[]");
    }
}

TEST_CASE("failed asks roll history back to the per-turn checkpoint") {
    FakeEndpoint endpoint;
    endpoint.chats = {ok_reply("第一答"),
                      {.status = 500, .body = "second failed"}};
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://x", "k", {}, 60000, {},
        [&](const auto &request) { return endpoint(request); }));
    REQUIRE(bot.ask("第一問"));
    const std::string before = bot.history_json();
    CHECK_FALSE(bot.ask("第二問"));
    CHECK(bot.history_json() == before);
}

TEST_CASE("ask appends the user message before transport then rolls it back") {
    aos::llms::Bot *observed = nullptr;
    aos::llms::LLM llm(
        "m", "http://x", "k", {}, 60000, {},
        [&](const auto &) {
            REQUIRE(observed != nullptr);
            const LlmsJson during = LlmsJson::parse(observed->history_json());
            REQUIRE(during.size() == 1);
            CHECK(during[0]["role"] == "user");
            return aos::llms::HttpResponse{.error = "offline"};
        });
    aos::llms::Bot bot(std::move(llm));
    observed = &bot;
    aos::llms::Reply reply = bot.ask("先寫進去");
    CHECK_FALSE(reply);
    CHECK(reply.checkpoint == 0);
    CHECK(bot.history_json() == "[]");
}

TEST_CASE("a wholly empty unfinished reply rolls the turn back in finish") {
    FakeEndpoint endpoint;
    endpoint.chats = {{
        .status = 200,
        .body = R"({"choices":[{"finish_reason":null,"message":{"content":null,"tool_calls":null}}]})"}};
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://x", "k", {}, 60000, {},
        [&](const auto &request) { return endpoint(request); }));
    aos::llms::Reply reply = bot.ask("不該留下");
    REQUIRE(reply);
    CHECK(reply.text.empty());
    CHECK_FALSE(reply.finish_reason.has_value());
    CHECK(bot.history_json() == "[]");
}

TEST_CASE("tool_choice without tools fails through Reply without transport") {
    int calls = 0;
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://x", "k", {}, 60000, {},
        [&](const auto &) {
            ++calls;
            return ok_reply();
        }));
    aos::llms::Ask request;
    request.prompt = "問";
    request.tool_choice_json = R"("required")";
    aos::llms::Reply reply = bot.ask(request);
    CHECK_FALSE(reply);
    CHECK(reply.err->kind == aos::llms::ErrorKind::InvalidArgument);
    CHECK(calls == 0);
    CHECK(bot.history_json() == "[]");
}

TEST_CASE("remember false leaves both sides of a successful turn out of history") {
    FakeEndpoint endpoint;
    endpoint.chats = {ok_reply()};
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://x", "k", {}, 60000, {},
        [&](const auto &request) { return endpoint(request); }));
    aos::llms::Ask request;
    request.prompt = "一次性";
    request.remember = false;
    REQUIRE(bot.ask(request));
    CHECK(bot.history_json() == "[]");
}
