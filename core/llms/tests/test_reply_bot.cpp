#include <aos/llms.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <stdexcept>
#include <string>

namespace {

aos::llms::HttpResponse tool_reply(const std::string &content,
                                   const std::string &arguments,
                                   bool include_usage = false) {
    LlmsJson body = {
        {"choices",
         {{{"finish_reason", "tool_calls"},
           {"message",
            {{"content", content.empty() ? LlmsJson(nullptr)
                                         : LlmsJson(content)},
             {"reasoning_content", "先想"},
             {"tool_calls",
              {{{"id", "call-1"},
                {"type", "function"},
                {"function", {{"name", "lookup"},
                               {"arguments", arguments}}}}}}}}}}},
    };
    if (include_usage) {
        body["usage"] = {
            {"prompt_tokens", 5},
            {"completion_tokens", 7},
            {"total_tokens", 12},
            {"prompt_tokens_details", {{"cached_tokens", 2}}},
            {"completion_tokens_details", {{"reasoning_tokens", 3}}},
        };
    }
    return {.status = 200, .body = body.dump()};
}

}  // namespace

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

TEST_CASE("Params extra cannot override model messages or non-stream mode") {
    FakeEndpoint endpoint;
    endpoint.chats = {ok_reply()};
    aos::llms::Params params;
    params.temperature = 0.2;
    params.extra_json =
        R"({"model":"wrong","messages":[{"role":"user","content":"wrong"}],"stream":true,"temperature":0.4})";
    aos::llms::Bot bot(aos::llms::LLM(
        "right", "http://x/v1", "k", params, 60000, {},
        [&](const auto &request) { return endpoint(request); }));
    REQUIRE(bot.ask("real"));
    const LlmsJson body = LlmsJson::parse(endpoint.requests.back().body);
    CHECK(endpoint.requests.back().method == "POST");
    CHECK(endpoint.requests.back().url == "http://x/v1/chat/completions");
    CHECK(endpoint.requests.back().headers[0] == "Authorization: Bearer k");
    CHECK(body["model"] == "right");
    CHECK(body["stream"] == false);
    CHECK(body["messages"].size() == 1);
    CHECK(body["messages"][0]["content"] == "real");
    CHECK(body["temperature"] == 0.4);
}

TEST_CASE("image-only asks are sent without requiring a prompt") {
    aos::llms::LLM::clear_caps_cache();
    FakeEndpoint endpoint;
    endpoint.chats = {ok_reply()};
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://images", "k", {}, 60000, {},
        [&](const auto &request) { return endpoint(request); }));
    aos::llms::Ask request;
    request.images = {"https://example.test/image.png"};
    REQUIRE(bot.ask(request));
    const LlmsJson body = LlmsJson::parse(endpoint.requests.back().body);
    REQUIRE(body["messages"].size() == 1);
    CHECK(body["messages"][0]["role"] == "user");
    CHECK(body["messages"][0]["content"][0]["text"] == "");
    CHECK(body["messages"][0]["content"][1]["image_url"]["url"] ==
          "https://example.test/image.png");
}

TEST_CASE("Reply exposes text and calls together and writes exact tool history") {
    FakeEndpoint endpoint;
    endpoint.chats = {tool_reply("好，我來查", R"({"q":"weather"})", true)};
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://x", "k", {}, 60000, {},
        [&](const auto &request) { return endpoint(request); }));
    aos::llms::Reply reply = bot.ask("查天氣");
    REQUIRE(reply);
    CHECK(reply.text == "好，我來查");
    REQUIRE(reply.calls.size() == 1);
    CHECK(reply.calls[0].name == "lookup");
    CHECK(reply.calls[0].args == R"({"q":"weather"})");
    REQUIRE(reply.reasoning.has_value());
    CHECK(*reply.reasoning == "先想");
    REQUIRE(reply.usage.has_value());
    CHECK(reply.usage->prompt == 5);
    CHECK(reply.usage->completion == 7);
    CHECK(reply.usage->total == 12);
    CHECK(reply.usage->cached == 2);
    CHECK(reply.usage->reasoning == 3);

    const LlmsJson history = LlmsJson::parse(bot.history_json());
    REQUIRE(history.size() == 2);
    CHECK(history[1]["content"] == "好，我來查");
    CHECK(history[1]["tool_calls"][0]["id"] == "call-1");
    CHECK(history[1]["tool_calls"][0]["type"] == "function");
    CHECK(history[1]["tool_calls"][0]["function"]["arguments"] ==
          R"({"q":"weather"})");
    REQUIRE(bot.pending_calls().size() == 1);
}

TEST_CASE("tool-only replies use null content and malformed args stay inspectable") {
    FakeEndpoint endpoint;
    endpoint.chats = {tool_reply("", "{broken")};
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://x", "k", {}, 60000, {},
        [&](const auto &request) { return endpoint(request); }));
    aos::llms::Reply reply = bot.ask("call it");
    REQUIRE(reply);
    REQUIRE(reply.calls.size() == 1);
    CHECK(reply.calls[0].args.empty());
    CHECK(reply.calls[0].args_raw == std::optional<std::string>("{broken"));
    const LlmsJson history = LlmsJson::parse(bot.history_json());
    CHECK(history[1]["content"].is_null());
    CHECK(history[1]["tool_calls"][0]["function"]["arguments"] ==
          "{broken");
}

TEST_CASE("pending calls clear after tool results and the next assistant reply") {
    FakeEndpoint endpoint;
    endpoint.chats = {tool_reply("", R"({"q":1})"), ok_reply("完成")};
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://x", "k", {}, 60000, {},
        [&](const auto &request) { return endpoint(request); }));
    REQUIRE(bot.ask("查"));
    REQUIRE(bot.pending_calls().size() == 1);
    aos::llms::Ask next;
    next.tool_results_json = R"({"call-1":"結果"})";
    next.prompt = "接著說";
    REQUIRE(bot.ask(next));
    CHECK(bot.pending_calls().empty());
    const LlmsJson request = LlmsJson::parse(endpoint.requests.back().body);
    CHECK(request["messages"][2]["role"] == "tool");
    CHECK(request["messages"][2]["tool_call_id"] == "call-1");
    CHECK(request["messages"][3]["role"] == "user");
}

TEST_CASE("system stays outside history and reset preserves it") {
    FakeEndpoint endpoint;
    endpoint.chats = {ok_reply("一"), ok_reply("二")};
    aos::llms::Bot bot(aos::llms::LLM(
                           "m", "http://x", "k", {}, 60000, {},
                           [&](const auto &request) { return endpoint(request); }),
                       "人格");
    REQUIRE(bot.ask("問"));
    const LlmsJson first_history = LlmsJson::parse(bot.history_json());
    CHECK(first_history.size() == 2);
    CHECK(first_history[0]["role"] == "user");
    const LlmsJson first_request = LlmsJson::parse(endpoint.requests[0].body);
    CHECK(first_request["messages"][0]["role"] == "system");
    CHECK(first_request["messages"][0]["content"] == "人格");

    bot.reset();
    CHECK(bot.history_json() == "[]");
    CHECK(bot.system() == std::optional<std::string>("人格"));
    REQUIRE(bot.ask("再問"));
    const LlmsJson second_request = LlmsJson::parse(endpoint.requests[1].body);
    CHECK(second_request["messages"][0]["role"] == "system");
}

TEST_CASE("missing usage members remain absent rather than zero") {
    FakeEndpoint endpoint;
    LlmsJson body = LlmsJson::parse(ok_reply().body);
    body["usage"] = {{"prompt_tokens", 9}};
    endpoint.chats = {{.status = 200, .body = body.dump()}};
    aos::llms::Bot bot(aos::llms::LLM(
        "m", "http://x", "k", {}, 60000, {},
        [&](const auto &request) { return endpoint(request); }));
    aos::llms::Reply reply = bot.ask("問");
    REQUIRE(reply.usage.has_value());
    CHECK(reply.usage->prompt == 9);
    CHECK_FALSE(reply.usage->completion.has_value());
    CHECK_FALSE(reply.usage->total.has_value());
    CHECK_FALSE(reply.usage->cached.has_value());
    CHECK_FALSE(reply.usage->reasoning.has_value());
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
