#include <aos/llms.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <stdexcept>

TEST_CASE("capabilities keep true false and unknown distinct") {
    aos::llms::LLM::clear_caps_cache();
    FakeEndpoint endpoint;
    endpoint.caps = {
        .status = 200,
        .body = R"({"data":[{"model_name":"m","model_info":{"supports_function_calling":false,"supports_prompt_caching":true}}]})"};
    aos::llms::LLM llm("m", "http://proxy/v1/chat/completions", "key",
                       {}, 60000, {},
                       [&](const auto &request) { return endpoint(request); });
    const aos::llms::Caps caps = llm.caps();
    REQUIRE(caps.tools.has_value());
    CHECK_FALSE(*caps.tools);
    CHECK_FALSE(caps.vision.has_value());
    REQUIRE(caps.caching.has_value());
    CHECK(*caps.caching);
    REQUIRE(endpoint.requests.size() == 1);
    CHECK(endpoint.requests[0].method == "GET");
    CHECK(endpoint.requests[0].url == "http://proxy/model/info");
    CHECK(endpoint.requests[0].headers ==
          std::vector<std::string>{"Authorization: Bearer key"});
    const auto models = llm.models();
    REQUIRE(models.size() == 1);
    CHECK(models[0].name == "m");

    CHECK(llm.check(true, false, false) == std::nullopt);
    const auto rejected = llm.check(false, true, false);
    REQUIRE(rejected.has_value());
    CHECK(rejected->kind == aos::llms::ErrorKind::Capability);
}

TEST_CASE("tool_choice without tools is an explicit local error") {
    int requests = 0;
    aos::llms::LLM llm(
        "m", "http://proxy", "key", {}, 60000, {},
        [&](const auto &) {
            ++requests;
            return unknown_caps();
        });
    const auto error = llm.check(false, false, true);
    REQUIRE(error.has_value());
    CHECK(error->kind == aos::llms::ErrorKind::InvalidArgument);
    CHECK(error->message.find("沒有 tools") != std::string::npos);
    CHECK(requests == 0);
}

TEST_CASE("capability override wins over the proxy table") {
    aos::llms::LLM::clear_caps_cache();
    FakeEndpoint endpoint;
    endpoint.caps = {
        .status = 200,
        .body = R"({"data":[{"model_name":"m","model_info":{"supports_vision":true}}]})"};
    aos::llms::Caps overrides;
    overrides.vision = false;
    aos::llms::LLM llm("m", "http://proxy", "key", {}, 60000,
                       overrides,
                       [&](const auto &request) { return endpoint(request); });
    CHECK(llm.supports(aos::llms::Capability::Vision) == false);
}

TEST_CASE("capability cache includes root and key and caches empty tables") {
    aos::llms::LLM::clear_caps_cache();
    int first_calls = 0;
    auto failing = [&](const aos::llms::HttpRequest &) {
        ++first_calls;
        return aos::llms::HttpResponse{.error = "offline"};
    };
    aos::llms::LLM first("m", "http://proxy/v1", "same", {}, 60000, {},
                         failing);
    CHECK_FALSE(first.supports(aos::llms::Capability::Vision).has_value());
    CHECK_FALSE(first.supports(aos::llms::Capability::Vision).has_value());
    CHECK(first_calls == 1);

    int same_key_calls = 0;
    aos::llms::LLM same("m", "http://proxy/chat/completions", "same", {},
                        60000, {}, [&](const auto &) {
                            ++same_key_calls;
                            return unknown_caps();
                        });
    CHECK_FALSE(same.supports(aos::llms::Capability::Tools).has_value());
    CHECK(same_key_calls == 0);

    int other_key_calls = 0;
    aos::llms::LLM other("m", "http://proxy", "other", {}, 60000, {},
                         [&](const auto &) {
                             ++other_key_calls;
                             return unknown_caps();
                         });
    CHECK_FALSE(other.supports(aos::llms::Capability::Tools).has_value());
    CHECK(other_key_calls == 1);

    aos::llms::LLM::clear_caps_cache();
    CHECK_FALSE(first.supports(aos::llms::Capability::Vision).has_value());
    CHECK(first_calls == 2);
}

TEST_CASE("capability lookup swallows thrown transports") {
    aos::llms::LLM::clear_caps_cache();
    aos::llms::LLM llm("m", "http://throwing", "key", {}, 60000, {},
                       [](const auto &) -> aos::llms::HttpResponse {
                           throw std::runtime_error("boom");
                       });
    CHECK_FALSE(llm.supports(aos::llms::Capability::Vision).has_value());
}

TEST_CASE("models() unions /model/info with the standard /models list") {
    // 直接打一個沒有 LiteLLM `/model/info` 的 OpenAI 相容端點（例如 LM Studio）。
    // 只查 `/model/info` 的話這裡會是一片空白。
    aos::llms::LLM::clear_caps_cache();
    aos::llms::LLM plain(
        "qwen/qwen3.5-9b", "http://lmstudio/v1", "key", {}, 60000, {},
        [](const aos::llms::HttpRequest &request) -> aos::llms::HttpResponse {
            if (request.url.ends_with("/model/info")) {
                return {.status = 404, .body = "not found"};
            }
            REQUIRE(request.url == "http://lmstudio/v1/models");
            return {.status = 200,
                    .body = R"({"data":[{"id":"qwen/qwen3.5-9b"},
                                        {"id":"google/gemma-4-e4b"}]})"};
        });

    const std::vector<aos::llms::ModelInfo> models = plain.models();
    REQUIRE(models.size() == 2);
    CHECK(models[0].name == "google/gemma-4-e4b");
    CHECK(models[1].name == "qwen/qwen3.5-9b");
    // 能力答不出來就是「不知道」，不是 false。
    CHECK_FALSE(models[0].caps.tools.has_value());
    CHECK_FALSE(models[1].caps.vision.has_value());
}

TEST_CASE("models() keeps proxy capabilities for names both sources report") {
    aos::llms::LLM::clear_caps_cache();
    aos::llms::LLM proxy(
        "m", "http://proxy", "key", {}, 60000, {},
        [](const aos::llms::HttpRequest &request) -> aos::llms::HttpResponse {
            if (request.url.ends_with("/model/info")) {
                return {.status = 200,
                        .body = R"({"data":[{"model_name":"m",
                            "model_info":{"supports_function_calling":true}}]})"};
            }
            return {.status = 200,
                    .body = R"({"data":[{"id":"m"},{"id":"only-in-list"}]})"};
        });

    const std::vector<aos::llms::ModelInfo> models = proxy.models();
    REQUIRE(models.size() == 2);
    CHECK(models[0].name == "m");
    CHECK(models[0].caps.tools == true);
    CHECK(models[1].name == "only-in-list");
    CHECK_FALSE(models[1].caps.tools.has_value());
}
