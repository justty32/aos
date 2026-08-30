#include <aos/llm.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <optional>
#include <string>
#include <vector>

extern "C" int aos_llm_cli_main(int, char **);

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

class ScopedSetEnv {
public:
    ScopedSetEnv(const char *name, const char *value) : name_(name) {
        if (const char *old = std::getenv(name)) old_ = old;
        REQUIRE(setenv(name, value, 1) == 0);
    }

    ~ScopedSetEnv() {
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

int run_cli(std::vector<std::string> arguments) {
    std::vector<char *> argv;
    argv.reserve(arguments.size());
    for (std::string &argument : arguments) argv.push_back(argument.data());
    return aos_llm_cli_main(static_cast<int>(argv.size()), argv.data());
}

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

TEST_CASE("llm command options have local slot defaults") {
    ScopedUnsetEnv engine("AOS_LLM_ENGINE");
    ScopedUnsetEnv priority("AOS_LLM_PRIORITY");

    const aos::llm::CommandOptions command =
        aos::llm::parse_arguments({});
    CHECK(command.engine == "lmstudio");
    CHECK(command.priority == 0);
    CHECK_FALSE(command.slots);
}

TEST_CASE("llm slot environment defaults can be overridden") {
    ScopedSetEnv engine("AOS_LLM_ENGINE", "deepseek");
    ScopedSetEnv priority("AOS_LLM_PRIORITY", "7");

    const aos::llm::CommandOptions from_environment =
        aos::llm::parse_arguments({});
    CHECK(from_environment.engine == "deepseek");
    CHECK(from_environment.priority == 7);

    const aos::llm::CommandOptions from_arguments =
        aos::llm::parse_arguments(
            {"--engine", "x", "--priority", "-3"});
    CHECK(from_arguments.engine == "x");
    CHECK(from_arguments.priority == -3);
}

TEST_CASE("llm arguments enable slot status") {
    const aos::llm::CommandOptions command =
        aos::llm::parse_arguments({"--slots"});
    CHECK(command.slots);

    const aos::llm::CommandOptions with_messages =
        aos::llm::parse_arguments(
            {"--system", "s", "--messages", "m.json", "--slots"});
    CHECK(with_messages.slots);
}

TEST_CASE("llm arguments reject malformed slot options") {
    CHECK_THROWS_AS(aos::llm::parse_arguments({"--priority", "abc"}),
                    std::invalid_argument);
    CHECK_THROWS_AS(aos::llm::parse_arguments({"--priority", ""}),
                    std::invalid_argument);
    CHECK_THROWS_AS(aos::llm::parse_arguments({"--engine", ""}),
                    std::invalid_argument);
}

TEST_CASE("llm ignores malformed priority environment value") {
    ScopedSetEnv priority("AOS_LLM_PRIORITY", "zzz");

    const aos::llm::CommandOptions command =
        aos::llm::parse_arguments({});
    CHECK(command.priority == 0);
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

TEST_CASE("llm extracts the served model when present") {
    CHECK(aos::llm::parse_response_model(
              R"({"model":"qwen/qwen3.5-9b","choices":[]})") ==
          "qwen/qwen3.5-9b");
    CHECK(aos::llm::parse_response_model(R"({"choices":[]})").empty());
}

TEST_CASE("llm CLI help succeeds without contacting an endpoint") {
    CHECK(run_cli({"aos llm", "--url", "http://127.0.0.1:1/v1",
                   "--help"}) == 0);
}
