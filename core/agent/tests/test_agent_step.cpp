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
#include <unistd.h>

namespace {

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
        aos::agent::initialize(path, "bob");
        std::filesystem::remove_all(path / ".aos" / "inbox");
        std::filesystem::create_directories(path / ".aos" / "inbox");
    }
    ~TempWorld() { std::filesystem::remove_all(path); }
    std::filesystem::path path;
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
    CHECK(std::filesystem::exists(world.path / ".aos" / "inbox" /
                                  "agent-bob-7.json"));
}

TEST_CASE("agent idle step skips completion but requeues itself") {
    TempWorld world;
    ScopedTurn turn("8");
    bool called = false;
    CHECK(aos::agent::step(
              world.path, "bob",
              [&](const std::vector<aos::agent::Message> &) {
                  called = true;
                  return "不應出現";
              }) == 0);
    CHECK_FALSE(called);
    CHECK(std::filesystem::exists(world.path / ".aos" / "inbox" /
                                  "agent-bob-8.json"));
    CHECK(aos::agent::read_status(world.path, "bob").status == "idle");
}

TEST_CASE("agent tool trip uses pending turn plus one and resumes later") {
    TempWorld world;
    {
        ScopedTurn turn("10");
        aos::agent::say(world.path, "bob", "列出檔案");
        REQUIRE(aos::agent::step(
                    world.path, "bob",
                    [](const std::vector<aos::agent::Message> &) {
                        return "我先查看。\n{\"tool\":\"ls\",\"args\":\"-la\"}";
                    }) == 0);
    }
    const aos::agent::Pending pending =
        aos::agent::read_pending(world.path, "bob");
    REQUIRE(pending.turn == 10);
    REQUIRE(pending.calls.size() == 1);
    const auto instruction = world.path / ".aos" / "inbox" /
                             (pending.calls[0].id + ".json");
    REQUIRE(std::filesystem::exists(instruction));

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
                                message.content.find("alpha") != std::string::npos) {
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
    CHECK(history.back().content == "結果裡有 alpha 和 beta。");
    CHECK(std::filesystem::exists(world.path / ".aos" / "inbox" /
                                  "agent-bob-12.json"));
}

TEST_CASE("agent completion failure still requeues itself") {
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
    CHECK(std::filesystem::exists(world.path / ".aos" / "inbox" /
                                  "agent-bob-13.json"));
    CHECK(aos::agent::read_status(world.path, "bob").status == "idle");
}
