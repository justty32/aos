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
#include <sys/stat.h>
#include <vector>
#include <unistd.h>

namespace {

class ScopedEnvironment {
public:
    ScopedEnvironment(const char *name, const std::string &value) : name_(name) {
        if (const char *old = std::getenv(name)) old_ = old;
        REQUIRE(setenv(name, value.c_str(), 1) == 0);
    }

    ~ScopedEnvironment() {
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

class TempWorld {
public:
    TempWorld() {
        const auto stamp = std::chrono::steady_clock::now()
                               .time_since_epoch()
                               .count();
        path = std::filesystem::temp_directory_path() /
               ("aos-agent-lifecycle-" + std::to_string(getpid()) + "-" +
                std::to_string(stamp));
        std::filesystem::create_directories(path);
        aos_home_.emplace("AOS_HOME", (path / "aos-home").string());
    }

    ~TempWorld() { std::filesystem::remove_all(path); }

    std::filesystem::path path;

private:
    std::optional<ScopedEnvironment> aos_home_;
};

std::filesystem::path agent_path(const TempWorld &world) {
    return world.path / ".aos" / "agents" / "bob";
}

std::string text_file(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input),
            std::istreambuf_iterator<char>()};
}

nlohmann::json json_file(const std::filesystem::path &path) {
    std::ifstream input(path);
    nlohmann::json value;
    input >> value;
    return value;
}

std::size_t say_count(const TempWorld &world) {
    return static_cast<std::size_t>(std::distance(
        std::filesystem::directory_iterator(agent_path(world) / "say"),
        std::filesystem::directory_iterator()));
}

}  // namespace

TEST_CASE("agent initialize 保留 lmstudio model") {
    TempWorld world;
    aos::agent::initialize(
        world.path, "bob", "測試人格。",
        aos::agent::Engine{.kind = "lmstudio", .model = "X"});

    const auto engine_path = agent_path(world) / "engine.json";
    CHECK(json_file(engine_path)["model"] == "X");
    const aos::agent::Engine engine =
        aos::agent::read_engine(world.path, "bob");
    CHECK(engine.kind == "lmstudio");
    CHECK(engine.model == "X");
}

TEST_CASE("agent completion 失敗保留未讀訊息與 history") {
    TempWorld world;
    ScopedEnvironment turn("AOS_TURN", "12");
    aos::agent::initialize(world.path, "bob");
    aos::agent::say(world.path, "bob", "不能遺失的交代");

    CHECK(aos::agent::step(
              world.path, "bob",
              [](const std::vector<aos::agent::Message> &) -> std::string {
                  throw std::runtime_error("假的 completion 失敗");
              }) == 1);
    CHECK(aos::agent::read_status(world.path, "bob").status == "error");
    CHECK(say_count(world) == 1);
    CHECK(aos::agent::read_history(world.path, "bob").empty());
}

TEST_CASE("agent completion 恢復後處理先前未讀訊息") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    aos::agent::say(world.path, "bob", "稍後仍要回答");
    {
        ScopedEnvironment turn("AOS_TURN", "13");
        REQUIRE(aos::agent::step(
                    world.path, "bob",
                    [](const std::vector<aos::agent::Message> &)
                        -> std::string {
                        throw std::runtime_error("暫時失敗");
                    }) == 1);
    }
    REQUIRE(say_count(world) == 1);

    bool saw_user = false;
    {
        ScopedEnvironment turn("AOS_TURN", "14");
        REQUIRE(aos::agent::step(
                    world.path, "bob",
                    [&](const std::vector<aos::agent::Message> &messages) {
                        saw_user = messages.back().role == "user" &&
                                   messages.back().content == "稍後仍要回答";
                        return "已經回答";
                    }) == 0);
    }

    CHECK(saw_user);
    CHECK(say_count(world) == 0);
    const auto history = aos::agent::read_history(world.path, "bob");
    REQUIRE(history.size() == 2);
    CHECK(history[0].content == "稍後仍要回答");
    CHECK(history[1].role == "assistant");
    CHECK(history[1].content == "已經回答");
}

TEST_CASE("agent 連線失敗寫入 log 與端點指引") {
    TempWorld world;
    ScopedEnvironment turn("AOS_TURN", "15");
    ScopedEnvironment url("AOS_LLM_URL", "http://localhost:19999/v1");
    aos::agent::initialize(world.path, "bob");
    aos::agent::say(world.path, "bob", "請處理");

    REQUIRE(aos::agent::step(
                world.path, "bob",
                [](const std::vector<aos::agent::Message> &) -> std::string {
                    throw std::runtime_error(
                        "LLM 連線失敗: Failed to connect");
                }) == 1);
    const std::string log = aos::agent::read_log(world.path, "bob");
    CHECK(log.find("> 第 15 回合失敗：LLM 連線失敗: Failed to connect") !=
          std::string::npos);
    CHECK(log.find("請確認 LLM 端點 http://localhost:19999/v1 是不是活的") !=
          std::string::npos);
    CHECK(log.find("AOS_LLM_URL") != std::string::npos);
}

TEST_CASE("agent pi 失敗回報 error 並保留未讀訊息") {
    TempWorld world;
    const auto fake_pi = world.path / "fake-pi-failure.sh";
    {
        std::ofstream output(fake_pi, std::ios::binary | std::ios::trunc);
        output << "#!/bin/sh\n"
                  "cat >/dev/null\n"
                  "echo 'No API key found for deepseek. Use /login' >&2\n"
                  "exit 3\n";
    }
    REQUIRE(chmod(fake_pi.c_str(), 0755) == 0);
    ScopedEnvironment pi_bin("AOS_PI_BIN", fake_pi.string());
    ScopedEnvironment turn("AOS_TURN", "16");
    aos::agent::initialize(world.path, "bob", "測試人格。",
                           aos::agent::Engine{.kind = "pi"});
    aos::agent::say(world.path, "bob", "不能遺失的 pi 交代");

    CHECK(aos::agent::step(world.path, "bob") == 1);
    const aos::agent::Status status =
        aos::agent::read_status(world.path, "bob");
    CHECK(status.status == "error");
    CHECK(status.detail ==
          "pi 失敗（exit=3）：No API key found for deepseek. Use /login");
    CHECK(say_count(world) == 1);
    CHECK(aos::agent::read_history(world.path, "bob").empty());
    const std::string log = aos::agent::read_log(world.path, "bob");
    CHECK(log.find("DEEPSEEK_API_KEY") != std::string::npos);
}

TEST_CASE("agent log journal 依舊格式渲染 log") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    aos::agent::say(world.path, "bob", "你好");
    {
        ScopedEnvironment turn("AOS_TURN", "4");
        REQUIRE(aos::agent::step(
                    world.path, "bob",
                    [](const std::vector<aos::agent::Message> &) {
                        return "完成\n";
                    }) == 0);
    }
    aos::agent::say(world.path, "bob", "這封要保留");
    {
        ScopedEnvironment turn("AOS_TURN", "5");
        REQUIRE(aos::agent::step(
                    world.path, "bob",
                    [](const std::vector<aos::agent::Message> &)
                        -> std::string {
                        throw std::runtime_error("註記");
                    }) == 1);
    }

    const std::string expected =
        "## turn 4 user\n你好\n\n"
        "## turn 4 assistant\n完成\n\n"
        "> 第 5 回合失敗：註記\n";
    const auto log = agent_path(world) / "log.md";
    const auto journal_path = agent_path(world) / "log.jsonl";
    CHECK(text_file(log) == expected);
    const std::string journal = text_file(journal_path);
    CHECK(std::count(journal.begin(), journal.end(), '\n') == 3);

    std::vector<std::string> roles;
    std::ifstream input(journal_path);
    std::string line;
    while (std::getline(input, line)) {
        roles.push_back(nlohmann::json::parse(line)["role"]);
    }
    CHECK(roles == std::vector<std::string>{"user", "assistant", "note"});
}

TEST_CASE("agent read_log 偵測竄改並還原 log") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    aos::agent::say(world.path, "bob", "請回答");
    {
        ScopedEnvironment turn("AOS_TURN", "6");
        REQUIRE(aos::agent::step(
                    world.path, "bob",
                    [](const std::vector<aos::agent::Message> &) {
                        return "真正回覆";
                    }) == 0);
    }
    const auto log = agent_path(world) / "log.md";
    const std::string canonical = text_file(log);
    {
        std::ofstream output(log, std::ios::binary | std::ios::app);
        output << "## turn 99 assistant\n假回覆\n";
    }

    const std::string restored = aos::agent::read_log(world.path, "bob");
    CHECK(restored == canonical);
    CHECK(restored.find("turn 99") == std::string::npos);
    CHECK(text_file(log) == canonical);
}

TEST_CASE("agent read_log 相容沒有 journal 的舊世界") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    const auto log = agent_path(world) / "log.md";
    const auto journal = agent_path(world) / "log.jsonl";
    std::filesystem::remove(journal);
    {
        std::ofstream output(log, std::ios::binary | std::ios::trunc);
        output << "舊世界原文\n";
    }

    CHECK(aos::agent::read_log(world.path, "bob") == "舊世界原文\n");
    CHECK_FALSE(std::filesystem::exists(journal));
}

TEST_CASE("agent init 把 aos 的絕對路徑寫進 every") {
    TempWorld world;
    const auto binary = world.path / "fake-aos" / "aos";
    std::filesystem::create_directories(binary.parent_path());
    {
        std::ofstream output(binary, std::ios::binary | std::ios::trunc);
        output << "#!/bin/sh\nexit 0\n";
    }
    ::chmod(binary.c_str(), 0755);

    // L1-01：every/ 裡的裸 "aos" 會讓 PATH 上沒有 aos 的人每回合 exit 127。
    ScopedEnvironment aos_bin("AOS_BIN", binary.string());
    aos::agent::initialize(world.path, "bob");

    const nlohmann::json instruction = nlohmann::json::parse(text_file(
        world.path / ".aos" / "every" / "agent-bob.json"));
    REQUIRE(instruction.contains("argv"));
    CHECK(instruction["argv"][0].get<std::string>() == binary.string());
    CHECK(instruction["argv"][1].get<std::string>() == "agent");
    CHECK(instruction["argv"][2].get<std::string>() == "step");
}
