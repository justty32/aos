#include <aos/agent.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <optional>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

namespace {

class TempWorld {
public:
    TempWorld() {
        const auto stamp = std::chrono::steady_clock::now()
                               .time_since_epoch()
                               .count();
        path = std::filesystem::temp_directory_path() /
               ("aos-agent-engine-" + std::to_string(getpid()) + "-" +
                std::to_string(stamp));
        std::filesystem::create_directories(path);
    }
    ~TempWorld() { std::filesystem::remove_all(path); }
    std::filesystem::path path;
};

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

nlohmann::json json_file(const std::filesystem::path &path) {
    std::ifstream input(path);
    nlohmann::json value;
    input >> value;
    return value;
}

void write_text(const std::filesystem::path &path, std::string_view text) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    output.write(text.data(), static_cast<std::streamsize>(text.size()));
}

std::filesystem::path write_script(const TempWorld &world,
                                   std::string_view name,
                                   std::string_view script) {
    const auto path = std::filesystem::absolute(world.path / name);
    write_text(path, script);
    REQUIRE(chmod(path.c_str(), 0755) == 0);
    return path;
}

bool say_is_empty(const TempWorld &world) {
    const auto say = world.path / ".aos" / "agents" / "bob" / "say";
    return std::filesystem::directory_iterator(say) ==
           std::filesystem::directory_iterator();
}

}  // namespace

TEST_CASE("agent init writes the default lmstudio engine") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");

    const auto engine_path =
        world.path / ".aos" / "agents" / "bob" / "engine.json";
    REQUIRE(std::filesystem::is_regular_file(engine_path));
    CHECK(json_file(engine_path) == nlohmann::json{{"engine", "lmstudio"}});
    CHECK(aos::agent::read_engine(world.path, "bob").kind == "lmstudio");
}

TEST_CASE("agent init fills pi engine defaults") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob", "測試人格。",
                           aos::agent::Engine{"pi"});

    const auto engine_path =
        world.path / ".aos" / "agents" / "bob" / "engine.json";
    const nlohmann::json stored = json_file(engine_path);
    CHECK(stored["engine"] == "pi");
    CHECK(stored["provider"] == "deepseek");
    CHECK(stored["model"] == "deepseek-v4-flash");
    REQUIRE(stored["session_id"].is_string());
    CHECK(stored["session_id"].get<std::string>().size() == 36);

    const aos::agent::Engine engine = aos::agent::read_engine(world.path, "bob");
    CHECK(engine.kind == "pi");
    CHECK(engine.provider == "deepseek");
    CHECK(engine.model == "deepseek-v4-flash");
    CHECK(engine.session_id.size() == 36);
}

TEST_CASE("agent missing engine file falls back to lmstudio") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    std::filesystem::remove(world.path / ".aos" / "agents" / "bob" /
                            "engine.json");

    CHECK_NOTHROW(aos::agent::read_engine(world.path, "bob"));
    CHECK(aos::agent::read_engine(world.path, "bob").kind == "lmstudio");
}

TEST_CASE("agent rejects an unknown engine") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    write_text(world.path / ".aos" / "agents" / "bob" / "engine.json",
               R"({"engine":"nope"})");

    CHECK_THROWS_AS(aos::agent::read_engine(world.path, "bob"),
                    std::runtime_error);
}

TEST_CASE("agent parses pi JSONL reply and tool calls") {
    const std::string jsonl =
        R"({"type":"session","id":"fake","cwd":"/tmp/world"})" "\n"
        R"({"type":"message_update","delta":"忽略"})" "\n"
        R"({"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"第一輪"}]}})" "\n"
        "這一行故意不是 JSON\n"
        R"({"type":"tool_execution_start","toolCallId":"call_1","toolName":"write","args":{"path":"hello.txt","content":"hi"}})" "\n"
        R"({"type":"message_update","delta":"仍然忽略"})" "\n"
        R"({"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"最後"},{"type":"toolCall","name":"write"},{"type":"text","text":"回覆"}]}})" "\n";

    aos::agent::PiRun run;
    CHECK_NOTHROW(run = aos::agent::parse_pi_stream(jsonl));
    CHECK(run.reply == "最後回覆");
    CHECK(run.tool_calls == std::vector<std::string>{"write hello.txt"});
}

TEST_CASE("agent pi step runs the configured executable in the world") {
    TempWorld world;
    ScopedEnvironment aos_home("AOS_HOME",
                               (world.path / "aos-home").string());
    const auto script = write_script(
        world, "fake-pi.sh",
        R"(#!/bin/sh
cat >/dev/null
touch from-fake-pi.txt
cat <<'EOF'
{"type":"message_update","delta":"忽略"}
{"type":"tool_execution_start","toolCallId":"call_1","toolName":"write","args":{"path":"from-fake-pi.txt"}}
{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"假 pi 已完成"}]}}
EOF
exit 0
)");
    ScopedEnvironment pi_bin("AOS_PI_BIN", script.string());
    ScopedEnvironment turn("AOS_TURN", "21");
    aos::agent::initialize(world.path, "bob", "測試人格。",
                           aos::agent::Engine{"pi"});
    aos::agent::say(world.path, "bob", "做點事");

    CHECK(aos::agent::step(world.path, "bob") == 0);
    CHECK(std::filesystem::exists(world.path / "from-fake-pi.txt"));
    const std::string log = aos::agent::read_log(world.path, "bob");
    CHECK(log.find("假 pi 已完成") != std::string::npos);
    CHECK(log.find("## turn 21 user") != std::string::npos);
    CHECK(log.find("## turn 21 assistant") != std::string::npos);
    CHECK(say_is_empty(world));
    // 存活靠 .aos/every/（隊 C 的常駐投遞），step 自己不再投遞下一次。
    CHECK(std::filesystem::exists(world.path / ".aos" / "every" /
                                  "agent-bob.json"));
    CHECK(aos::agent::read_status(world.path, "bob").status == "idle");
}

TEST_CASE("agent pi failure records a note and stays alive") {
    TempWorld world;
    ScopedEnvironment aos_home("AOS_HOME",
                               (world.path / "aos-home").string());
    const auto script = write_script(
        world, "fake-pi-failure.sh",
        R"(#!/bin/sh
cat >/dev/null
echo boom >&2
exit 3
)");
    ScopedEnvironment pi_bin("AOS_PI_BIN", script.string());
    ScopedEnvironment turn("AOS_TURN", "22");
    aos::agent::initialize(world.path, "bob", "測試人格。",
                           aos::agent::Engine{"pi"});
    aos::agent::say(world.path, "bob", "觸發失敗");

    // L1-17：pi 失敗就是這一回合失敗，step 要回非 0，loop 才看得見。
    CHECK(aos::agent::step(world.path, "bob") == 1);
    const std::string log = aos::agent::read_log(world.path, "bob");
    CHECK(log.find("pi 失敗") != std::string::npos);
    CHECK(log.find("boom") != std::string::npos);
    CHECK(std::filesystem::exists(world.path / ".aos" / "every" /
                                  "agent-bob.json"));
    CHECK(aos::agent::read_status(world.path, "bob").status == "error");
    CHECK(aos::agent::read_status(world.path, "bob").detail.starts_with(
        "pi 失敗（exit=3）"));
}

TEST_CASE("agent pi step reports unavailable slots as temporary") {
    TempWorld world;
    const auto aos_home_path = world.path / "aos-home";
    ScopedEnvironment aos_home("AOS_HOME", aos_home_path.string());
    std::filesystem::create_directories(aos_home_path);
    write_text(aos_home_path / "cpus.json",
               R"({"deepseek":{"max_inflight":0,"wait_ms":0}})");
    ScopedEnvironment turn("AOS_TURN", "23");
    aos::agent::initialize(world.path, "bob", "測試人格。",
                           aos::agent::Engine{"pi"});
    aos::agent::say(world.path, "bob", "稍後再做");

    CHECK(aos::agent::step(world.path, "bob") == 75);
    CHECK(aos::agent::read_status(world.path, "bob").status ==
          "waiting-llm");
    CHECK_FALSE(say_is_empty(world));
}
