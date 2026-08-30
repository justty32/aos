#include <aos/agent.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>
#include <unistd.h>

extern "C" int aos_agent_cli_main(int argc, char *argv[]);

namespace {

class ScopedEnvironment {
public:
    ScopedEnvironment(const char *name, const std::string &value) : name_(name) {
        if (const char *old = std::getenv(name)) old_ = old;
        REQUIRE(setenv(name, value.c_str(), 1) == 0);
    }
    ~ScopedEnvironment() {
        if (old_) setenv(name_.c_str(), old_->c_str(), 1);
        else unsetenv(name_.c_str());
    }

private:
    std::string name_;
    std::optional<std::string> old_;
};

class TempWorld {
public:
    TempWorld() {
        const auto stamp = std::chrono::steady_clock::now()
                               .time_since_epoch()
                               .count();
        path = std::filesystem::temp_directory_path() /
               ("aos-agent-step-" + std::to_string(getpid()) + "-" +
                std::to_string(stamp));
        std::filesystem::create_directories(path);
        aos_home_.emplace("AOS_HOME", (path / "aos-home").string());
        aos::agent::initialize(path, "bob");
        std::filesystem::remove_all(path / ".aos" / "inbox");
        std::filesystem::create_directories(path / ".aos" / "inbox");
    }
    ~TempWorld() { std::filesystem::remove_all(path); }
    std::filesystem::path path;

private:
    std::optional<ScopedEnvironment> aos_home_;
};

class ScopedTurn {
public:
    explicit ScopedTurn(const char *value) {
        if (const char *old = std::getenv("AOS_TURN")) old_ = old;
        REQUIRE(setenv("AOS_TURN", value, 1) == 0);
    }
    ~ScopedTurn() {
        if (old_) setenv("AOS_TURN", old_->c_str(), 1);
        else unsetenv("AOS_TURN");
    }
private:
    std::optional<std::string> old_;
};

void write_json(const std::filesystem::path &path,
                const nlohmann::json &value) {
    std::filesystem::create_directories(path.parent_path());
    const auto temporary = path.string() + ".tmp";
    std::ofstream output(temporary);
    output << value.dump();
    output.close();
    std::filesystem::rename(temporary, path);
}

bool has_step_instruction(const std::filesystem::path &inbox) {
    for (const auto &entry : std::filesystem::directory_iterator(inbox)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".json") {
            continue;
        }
        std::ifstream input(entry.path());
        nlohmann::json instruction;
        input >> instruction;
        const auto argv =
            instruction.value("argv", std::vector<std::string>{});
        if (argv.size() >= 3 && argv[0] == "aos" && argv[1] == "agent" &&
            argv[2] == "step") {
            return true;
        }
    }
    return false;
}

nlohmann::json json_file(const std::filesystem::path &path) {
    std::ifstream input(path);
    nlohmann::json value;
    input >> value;
    return value;
}

std::string text_file(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input),
            std::istreambuf_iterator<char>()};
}

int run_agent_cli(std::vector<std::string> arguments) {
    std::vector<char *> argv;
    argv.reserve(arguments.size());
    for (std::string &argument : arguments) argv.push_back(argument.data());
    return aos_agent_cli_main(static_cast<int>(argv.size()), argv.data());
}

}  // namespace

TEST_CASE("agent step calls completion for say and records the reply") {
    TempWorld world;
    ScopedTurn turn("7");
    aos::agent::say(world.path, "bob", "你好");
    bool called = false;
    const int result = aos::agent::step(
        world.path, "bob",
        [&](const std::vector<aos::agent::Message> &messages) {
            called = true;
            REQUIRE(messages.front().role == "system");
            CHECK(messages.front().content.find("- ls — 列出資料夾內容。") !=
                  std::string::npos);
            CHECK(messages.front().content.find(
                      "(args: list, stdin: none, 可預期性: high)") !=
                  std::string::npos);
            CHECK(messages.back().role == "user");
            CHECK(messages.back().content == "你好");
            return "我叫 bob。";
        });

    CHECK(result == 0);
    CHECK(called);
    const auto history = aos::agent::read_history(world.path, "bob");
    REQUIRE(history.size() == 2);
    CHECK(history[0].role == "user");
    CHECK(history[1].role == "assistant");
    CHECK(aos::agent::read_log(world.path, "bob").find("我叫 bob。") !=
          std::string::npos);
    CHECK(std::filesystem::is_empty(world.path / ".aos" / "inbox"));
}

TEST_CASE("agent step keeps say when the lmstudio slot is unavailable") {
    TempWorld world;
    write_json(world.path / "aos-home" / "cpus.json",
               {{"lmstudio", {{"max_inflight", 0}, {"wait_ms", 0}}}});
    ScopedTurn turn("31");
    aos::agent::say(world.path, "bob", "稍後再處理");
    const auto say = world.path / ".aos" / "agents" / "bob" / "say";
    REQUIRE_FALSE(std::filesystem::is_empty(say));

    bool called = false;
    CHECK(aos::agent::step(world.path, "bob",
                           [&](const std::vector<aos::agent::Message> &) {
                               called = true;
                               return "不應呼叫";
                           }) == 75);
    CHECK_FALSE(called);
    CHECK(aos::agent::read_status(world.path, "bob").status ==
          "waiting-llm");
    CHECK_FALSE(std::filesystem::is_empty(say));
}

TEST_CASE("agent step completes while holding an available lmstudio slot") {
    TempWorld world;
    write_json(world.path / "aos-home" / "cpus.json",
               {{"lmstudio", {{"max_inflight", 1}, {"wait_ms", 1000}}}});
    ScopedTurn turn("32");
    aos::agent::say(world.path, "bob", "現在處理");

    bool called = false;
    CHECK(aos::agent::step(world.path, "bob",
                           [&](const std::vector<aos::agent::Message> &) {
                               called = true;
                               return "已處理";
                           }) == 0);
    CHECK(called);
    const auto history = aos::agent::read_history(world.path, "bob");
    REQUIRE_FALSE(history.empty());
    CHECK(history.back().role == "assistant");
}

TEST_CASE("agent init stores nonzero priority and omits the default") {
    TempWorld world;
    const auto prioritized = world.path / "prioritized";
    std::filesystem::create_directories(prioritized);
    CHECK(run_agent_cli({"aos agent", "init", prioritized.string(), "--name",
                         "alice", "--provider", "gpu", "--priority", "7"}) ==
          0);

    const auto prioritized_engine =
        prioritized / ".aos" / "agents" / "alice" / "engine.json";
    CHECK(aos::agent::read_engine(prioritized, "alice").priority == 7);
    CHECK(aos::agent::read_engine(prioritized, "alice").provider == "gpu");
    CHECK(text_file(prioritized_engine).find("\"priority\"") !=
          std::string::npos);

    const auto negative = world.path / "negative";
    std::filesystem::create_directories(negative);
    CHECK(run_agent_cli({"aos agent", "init", negative.string(), "--name",
                         "erin", "--priority", "-3"}) == 0);
    CHECK(aos::agent::read_engine(negative, "erin").priority == -3);

    const auto defaults = world.path / "defaults";
    std::filesystem::create_directories(defaults);
    aos::agent::initialize(defaults, "carol");
    const auto default_engine =
        defaults / ".aos" / "agents" / "carol" / "engine.json";
    CHECK(aos::agent::read_engine(defaults, "carol").priority == 0);
    CHECK(text_file(default_engine).find("\"priority\"") ==
          std::string::npos);

    const auto pi = world.path / "pi";
    std::filesystem::create_directories(pi);
    aos::agent::initialize(
        pi, "dave", "測試人格。",
        aos::agent::Engine{.kind = "pi", .priority = -4});
    const auto pi_engine = pi / ".aos" / "agents" / "dave" / "engine.json";
    CHECK(aos::agent::read_engine(pi, "dave").priority == -4);
    CHECK(json_file(pi_engine)["priority"] == -4);
}

TEST_CASE("agent rejects a noninteger engine priority") {
    TempWorld world;
    const auto engine =
        world.path / ".aos" / "agents" / "bob" / "engine.json";
    write_json(engine, {{"engine", "lmstudio"}, {"priority", "high"}});
    CHECK_THROWS_AS(aos::agent::read_engine(world.path, "bob"),
                    std::runtime_error);
}

TEST_CASE("agent idle step skips completion without self delivery") {
    TempWorld world;
    ScopedTurn turn("8");
    bool called = false;
    CHECK(aos::agent::step(world.path, "bob",
                           [&](const std::vector<aos::agent::Message> &) {
                               called = true;
                               return "不應出現";
                           }) == 0);
    CHECK_FALSE(called);
    CHECK(std::filesystem::is_empty(world.path / ".aos" / "inbox"));
    CHECK(aos::agent::read_status(world.path, "bob").status == "idle");
}

TEST_CASE("agent tool trip uses pending turn plus one and resumes later") {
    TempWorld world;
    {
        ScopedTurn turn("10");
        aos::agent::say(world.path, "bob", "列出檔案");
        REQUIRE(
            aos::agent::step(
                world.path, "bob",
                [](const std::vector<aos::agent::Message> &) {
                    return "我先查看。\n{\"tool\":\"ls\",\"args\":[\"-la\"]}";
                }) == 0);
    }
    const aos::agent::Pending pending =
        aos::agent::read_pending(world.path, "bob");
    REQUIRE(pending.turn == 10);
    REQUIRE(pending.calls.size() == 1);
    CHECK(pending.calls[0].args_json == "[\"-la\"]");
    const auto instruction =
        world.path / ".aos" / "inbox" / (pending.calls[0].id + ".json");
    REQUIRE(std::filesystem::exists(instruction));
    const nlohmann::json queued = json_file(instruction);
    CHECK(queued["argv"] == nlohmann::json::array({"ls", "-la"}));
    CHECK(queued["cwd"] == ".");
    CHECK(queued["timeout_ms"] == 30000);
    CHECK(json_file(world.path / ".aos" / "agents" / "bob" /
                    "pending.json")["calls"][0]["args"] ==
          nlohmann::json::array({"-la"}));

    write_json(world.path / ".aos" / "batch" / "11" / "out" /
                   (pending.calls[0].id + ".json"),
               {{"id", pending.calls[0].id},
                {"exit", 0},
                {"signal", nullptr},
                {"stdout", "alpha\nbeta\n"},
                {"stderr", ""}});

    bool saw_tool = false;
    {
        ScopedTurn turn("12");
        REQUIRE(aos::agent::step(
                    world.path, "bob",
                    [&](const std::vector<aos::agent::Message> &messages) {
                        for (const auto &message : messages) {
                            if (message.role == "tool" &&
                                message.content.find("alpha") !=
                                    std::string::npos) {
                                saw_tool = true;
                            }
                        }
                        return "結果裡有 alpha 和 beta。";
                    }) == 0);
    }
    CHECK(saw_tool);
    CHECK(aos::agent::read_pending(world.path, "bob").calls.empty());
    const auto history = aos::agent::read_history(world.path, "bob");
    CHECK(history[history.size() - 2].role == "tool");
    const nlohmann::json tool_message =
        nlohmann::json::parse(history[history.size() - 2].content);
    CHECK(tool_message["ok"] == true);
    CHECK(tool_message["tool"] == "ls");
    CHECK(tool_message["args"] == nlohmann::json::array({"-la"}));
    CHECK(tool_message["result"]["stdout"] == "alpha\nbeta\n");
    CHECK_FALSE(tool_message.contains("error"));
    CHECK(history.back().content == "結果裡有 alpha 和 beta。");
    CHECK_FALSE(has_step_instruction(world.path / ".aos" / "inbox"));
}

TEST_CASE("agent delivery uses registered cwd and timeout") {
    TempWorld world;
    aos::tool::Spec custom;
    custom.name = "custom";
    custom.argv = {"custom", "fixed"};
    custom.description = "自訂工具";
    custom.args = "none";
    custom.cwd = "subdir";
    custom.timeout_ms = 4321;
    aos::tool::write_spec(world.path, custom);

    ScopedTurn turn("14");
    aos::agent::say(world.path, "bob", "執行自訂工具");
    REQUIRE(aos::agent::step(world.path, "bob",
                             [](const std::vector<aos::agent::Message> &) {
                                 return "{\"tool\":\"custom\"}";
                             }) == 0);
    const aos::agent::Pending pending =
        aos::agent::read_pending(world.path, "bob");
    REQUIRE(pending.calls.size() == 1);
    CHECK(pending.calls[0].args_json == "null");
    const nlohmann::json instruction = json_file(
        world.path / ".aos" / "inbox" / (pending.calls[0].id + ".json"));
    CHECK(instruction["argv"] == nlohmann::json::array({"custom", "fixed"}));
    CHECK(instruction["cwd"] == "subdir");
    CHECK(instruction["timeout_ms"] == 4321);
}

TEST_CASE("agent omits tool instructions when its whitelist is empty") {
    TempWorld world;
    write_json(world.path / ".aos" / "agents" / "bob" / "tools.json",
               nlohmann::json::array());
    ScopedTurn turn("15");
    aos::agent::say(world.path, "bob", "正常回話");
    REQUIRE(aos::agent::step(
                world.path, "bob",
                [](const std::vector<aos::agent::Message> &messages) {
                    REQUIRE(messages.front().role == "system");
                    CHECK(messages.front().content.find("你可以使用工具") ==
                          std::string::npos);
                    CHECK(messages.front().content.find("可用工具") ==
                          std::string::npos);
                    return "正常回答。";
                }) == 0);
}

TEST_CASE("agent returns tool call errors and resumes thinking next step") {
    TempWorld world;
    {
        ScopedTurn turn("7");
        aos::agent::say(world.path, "bob", "用不存在的工具");
        REQUIRE(aos::agent::step(world.path, "bob",
                                 [](const std::vector<aos::agent::Message> &) {
                                     return "{\"tool\":\"nope\",\"args\":[]}";
                                 }) == 0);
    }

    auto history = aos::agent::read_history(world.path, "bob");
    REQUIRE_FALSE(history.empty());
    REQUIRE(history.back().role == "tool");
    const nlohmann::json error_message =
        nlohmann::json::parse(history.back().content);
    CHECK(error_message["call_id"] == "agent-bob-tool-7-0");
    CHECK(error_message["tool"] == "nope");
    CHECK(error_message["args"] == nlohmann::json::array());
    CHECK(error_message["ok"] == false);
    CHECK(error_message["result"].is_null());
    CHECK(error_message["error"]["type"] == "unknown_tool");
    CHECK(error_message["error"]["retryable"] == false);

    bool called = false;
    {
        ScopedTurn turn("8");
        REQUIRE(aos::agent::step(
                    world.path, "bob",
                    [&](const std::vector<aos::agent::Message> &messages) {
                        called = true;
                        const auto found = std::find_if(
                            messages.begin(), messages.end(),
                            [&](const aos::agent::Message &message) {
                                return message.role == "tool" &&
                                       message.content ==
                                           history.back().content;
                            });
                        CHECK(found != messages.end());
                        return "我會改用已登記的工具。";
                    }) == 0);
    }
    CHECK(called);
}

TEST_CASE("agent maps failed tool outcomes to fixed JSON errors") {
    TempWorld world;
    {
        ScopedTurn turn("20");
        aos::agent::say(world.path, "bob", "列出檔案");
        REQUIRE(aos::agent::step(world.path, "bob",
                                 [](const std::vector<aos::agent::Message> &) {
                                     return "{\"tool\":\"ls\",\"args\":[]}";
                                 }) == 0);
    }
    const aos::agent::Pending pending =
        aos::agent::read_pending(world.path, "bob");
    REQUIRE(pending.calls.size() == 1);

    SECTION("nonzero exit") {
        write_json(world.path / ".aos" / "batch" / "21" / "out" /
                       (pending.calls[0].id + ".json"),
                   {{"id", pending.calls[0].id},
                    {"exit", 3},
                    {"signal", nullptr},
                    {"stdout", ""},
                    {"stderr", "boom"}});
        ScopedTurn turn("22");
        REQUIRE(aos::agent::step(world.path, "bob",
                                 [](const std::vector<aos::agent::Message> &) {
                                     return "已看到失敗。";
                                 }) == 0);
        const auto history = aos::agent::read_history(world.path, "bob");
        const nlohmann::json message =
            nlohmann::json::parse(history[history.size() - 2].content);
        CHECK(message["ok"] == false);
        CHECK(message["error"]["type"] == "exit_nonzero");
        CHECK(message["error"]["retryable"] == false);
    }

    SECTION("timeout signal") {
        write_json(world.path / ".aos" / "batch" / "21" / "out" /
                       (pending.calls[0].id + ".json"),
                   {{"id", pending.calls[0].id},
                    {"exit", nullptr},
                    {"signal", 9},
                    {"stdout", ""},
                    {"stderr", ""}});
        ScopedTurn turn("22");
        REQUIRE(aos::agent::step(world.path, "bob",
                                 [](const std::vector<aos::agent::Message> &) {
                                     return "逾時了。";
                                 }) == 0);
        const auto history = aos::agent::read_history(world.path, "bob");
        const nlohmann::json message =
            nlohmann::json::parse(history[history.size() - 2].content);
        CHECK(message["ok"] == false);
        CHECK(message["error"]["type"] == "timeout");
        CHECK(message["error"]["retryable"] == true);
    }
}

TEST_CASE("agent completion failure does not self deliver") {
    TempWorld world;
    ScopedTurn turn("13");
    aos::agent::say(world.path, "bob", "觸發錯誤");
    std::string error;
    CHECK(aos::agent::step(
              world.path, "bob",
              [](const std::vector<aos::agent::Message> &) -> std::string {
                  throw std::runtime_error("假的 completion 失敗");
              },
              &error) == 1);
    CHECK(error == "假的 completion 失敗");
    CHECK(std::filesystem::is_empty(world.path / ".aos" / "inbox"));
    // L1-19：失敗的回合要留下 error，不能跟「沒事做」的 idle 長得一樣。
    CHECK(aos::agent::read_status(world.path, "bob").status == "error");
}
