#include <aos/llm.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <optional>
#include <string>
#include <vector>

namespace {

class ScopedUnsetEnv {
public:
    explicit ScopedUnsetEnv(const char *name) : name_(name) {
        if (const char *value = std::getenv(name)) old_ = value;
        REQUIRE(unsetenv(name) == 0);
    }

    ~ScopedUnsetEnv() {
        if (old_) {
            setenv(name_.c_str(), old_->c_str(), 1);
        } else {
            unsetenv(name_.c_str());
        }
    }

private:
    std::string name_;
    std::optional<std::string> old_;
};

}  // namespace

TEST_CASE("llm environment options have local defaults") {
    ScopedUnsetEnv url("AOS_LLM_URL");
    ScopedUnsetEnv model("AOS_LLM_MODEL");
    ScopedUnsetEnv key("AOS_LLM_KEY");

    const aos::llm::Options options = aos::llm::options_from_env();
    CHECK(options.url == "http://localhost:1234/v1");
    CHECK(options.model == "qwen/qwen3.5-9b");
    CHECK(options.key.empty());
    CHECK(options.timeout_ms == 120000);
}

TEST_CASE("llm environment options read configured values") {
    ScopedUnsetEnv url_guard("AOS_LLM_URL");
    ScopedUnsetEnv model_guard("AOS_LLM_MODEL");
    ScopedUnsetEnv key_guard("AOS_LLM_KEY");
    REQUIRE(setenv("AOS_LLM_URL", "http://example.test/v1", 1) == 0);
    REQUIRE(setenv("AOS_LLM_MODEL", "test-model", 1) == 0);
    REQUIRE(setenv("AOS_LLM_KEY", "secret", 1) == 0);

    const aos::llm::Options options = aos::llm::options_from_env();
    CHECK(options.url == "http://example.test/v1");
    CHECK(options.model == "test-model");
    CHECK(options.key == "secret");
}

TEST_CASE("llm arguments override completion options") {
    ScopedUnsetEnv url_guard("AOS_LLM_URL");
    ScopedUnsetEnv model_guard("AOS_LLM_MODEL");
    const std::vector<std::string> arguments = {
        "--system", "be brief", "--url", "http://server/v1",
        "--model", "another-model", "--timeout-ms", "45000"};

    const aos::llm::CommandOptions command =
        aos::llm::parse_arguments(arguments);
    REQUIRE(command.system);
    CHECK(*command.system == "be brief");
    CHECK_FALSE(command.messages_file);
    CHECK(command.completion.url == "http://server/v1");
    CHECK(command.completion.model == "another-model");
    CHECK(command.completion.timeout_ms == 45000);
}

TEST_CASE("llm arguments accept a messages file") {
    const aos::llm::CommandOptions command =
        aos::llm::parse_arguments({"--messages", "turn.json"});
    REQUIRE(command.messages_file);
    CHECK(*command.messages_file == "turn.json");
    CHECK_FALSE(command.system);
}

TEST_CASE("llm arguments reject ambiguous or malformed options") {
    CHECK_THROWS_AS(
        aos::llm::parse_arguments({"--system", "s", "--messages", "m.json"}),
        std::invalid_argument);
    CHECK_THROWS_AS(aos::llm::parse_arguments({"--timeout-ms", "0"}),
                    std::invalid_argument);
    CHECK_THROWS_AS(aos::llm::parse_arguments({"--url"}),
                    std::invalid_argument);
    CHECK_THROWS_AS(aos::llm::parse_arguments({"prompt"}),
                    std::invalid_argument);
}

TEST_CASE("llm parses and assembles OpenAI messages JSON") {
    const std::vector<aos::llm::Message> messages =
        aos::llm::parse_messages_json(
            R"([{"role":"system","content":"answer briefly"},{"role":"user","content":"hi"}])");
    REQUIRE(messages.size() == 2);
    CHECK(messages[0].role == "system");
    CHECK(messages[1].content == "hi");

    aos::llm::Options options;
    options.model = "unit-test-model";
    const nlohmann::json request =
        nlohmann::json::parse(aos::llm::make_request_json(messages, options));
    CHECK(request["model"] == "unit-test-model");
    CHECK(request["stream"] == false);
    CHECK(request["messages"].size() == 2);
    CHECK(request["messages"][0]["role"] == "system");
    CHECK(request["messages"][1]["content"] == "hi");
}

TEST_CASE("llm message parsing rejects a non-array or missing content") {
    CHECK_THROWS_AS(aos::llm::parse_messages_json(R"({"role":"user"})"),
                    std::runtime_error);
    CHECK_THROWS_AS(
        aos::llm::parse_messages_json(R"([{"role":"user"}])"),
        std::runtime_error);
}

TEST_CASE("llm extracts response content without going online") {
    CHECK(aos::llm::parse_response_text(
              R"({"choices":[{"message":{"content":"好"}}]})") ==
          "好");
    CHECK_THROWS_AS(aos::llm::parse_response_text(R"({"choices":[]})"),
                    std::runtime_error);
    CHECK_THROWS_AS(aos::llm::parse_response_text("not json"),
                    std::runtime_error);
}
