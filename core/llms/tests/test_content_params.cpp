#include <aos/llms.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdlib>
#include <optional>
#include <string>

namespace {

struct KeyEnvironment {
    KeyEnvironment() {
        const char *value = std::getenv("OPENAI_API_KEY");
        if (value != nullptr) old = value;
    }
    ~KeyEnvironment() {
        if (old) {
            setenv("OPENAI_API_KEY", old->c_str(), 1);
        } else {
            unsetenv("OPENAI_API_KEY");
        }
    }
    std::optional<std::string> old;
};

}  // namespace

TEST_CASE("llms normalizes completion and proxy root URLs") {
    using aos::llms::endpoint_root_url;
    using aos::llms::normalize_base_url;
    CHECK(normalize_base_url("http://host:4000/") == "http://host:4000");
    CHECK(normalize_base_url("http://host/v1/chat/completions/") ==
          "http://host/v1");
    CHECK(endpoint_root_url("http://host/v1/chat/completions") ==
          "http://host");
    CHECK(endpoint_root_url("http://host") == "http://host");
}

TEST_CASE("llms resolves explicit environment and fallback API keys") {
    KeyEnvironment restore;
    setenv("OPENAI_API_KEY", "env-key", 1);
    CHECK(aos::llms::resolve_key() == "env-key");
    CHECK(aos::llms::resolve_key(std::string("explicit")) == "explicit");
    unsetenv("OPENAI_API_KEY");
    CHECK(aos::llms::resolve_key() == "hello");
}

TEST_CASE("llms keeps remote images and base64 encodes local images") {
    CHECK(aos::llms::encode_image_url("https://example.test/a.png") ==
          "https://example.test/a.png");
    TempFile image(".jpg", "abc");
    CHECK(aos::llms::encode_image_url(image.path) ==
          "data:image/jpeg;base64,YWJj");
}

TEST_CASE("llms builds image-only content with an empty text part") {
    const LlmsJson content = LlmsJson::parse(aos::llms::build_content_json(
        std::nullopt, {"https://example.test/a.png"}));
    REQUIRE(content.is_array());
    REQUIRE(content.size() == 2);
    CHECK(content[0]["type"] == "text");
    CHECK(content[0]["text"] == "");
    CHECK(content[1]["image_url"]["url"] ==
          "https://example.test/a.png");
}

TEST_CASE("Params emits only configured fields") {
    aos::llms::Params params;
    params.temperature = 0.2;
    params.stop_json = R"(["END"] )";
    params.extra_json = R"({"reasoning_effort":"none"})";
    const LlmsJson value = LlmsJson::parse(params.to_json());
    CHECK(value.size() == 3);
    CHECK(value["temperature"] == 0.2);
    CHECK(value["stop"] == LlmsJson::array({"END"}));
    CHECK(value["reasoning_effort"] == "none");
    CHECK_FALSE(value.contains("top_p"));
    CHECK_FALSE(value.contains("max_tokens"));
}
