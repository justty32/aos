#include <aos/agent.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <optional>
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
               ("aos-agent-store-" + std::to_string(getpid()) + "-" +
                std::to_string(stamp));
        std::filesystem::create_directories(path);
    }
    ~TempWorld() { std::filesystem::remove_all(path); }
    std::filesystem::path path;
};

class ScopedCurrentPath {
public:
    explicit ScopedCurrentPath(const std::filesystem::path &path)
        : original_(std::filesystem::current_path()) {
        std::filesystem::current_path(path);
    }
    ~ScopedCurrentPath() { std::filesystem::current_path(original_); }

private:
    std::filesystem::path original_;
};

class ScopedUnsetFolder {
public:
    ScopedUnsetFolder() {
        if (const char *value = std::getenv("AOS_FOLDER")) original_ = value;
        unsetenv("AOS_FOLDER");
    }
    ~ScopedUnsetFolder() {
        if (original_) setenv("AOS_FOLDER", original_->c_str(), 1);
        else unsetenv("AOS_FOLDER");
    }

private:
    std::optional<std::string> original_;
};

nlohmann::json json_file(const std::filesystem::path &path) {
    std::ifstream input(path);
    nlohmann::json value;
    input >> value;
    return value;
}

}  // namespace

TEST_CASE("agent init creates its complete layout and every instruction") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob", "沉著的測試員。 ");
    const auto aos = world.path / ".aos";
    const auto agent = aos / "agents" / "bob";

    CHECK(std::filesystem::is_directory(aos / "inbox"));
    CHECK(std::filesystem::is_directory(aos / "every"));
    CHECK(std::filesystem::is_directory(agent / "say"));
    for (const char *name : {"persona.md", "history.json", "status.json",
                             "log.md", "tools.json", "pending.json"}) {
        CHECK(std::filesystem::is_regular_file(agent / name));
    }
    CHECK(std::filesystem::is_regular_file(aos / "turn"));
    CHECK(std::filesystem::is_regular_file(aos / "state.json"));

    CHECK(std::filesystem::is_empty(aos / "inbox"));
    const nlohmann::json instruction =
        json_file(aos / "every" / "agent-bob.json");
    const nlohmann::json expected = {
        {"argv", {"aos", "agent", "step"}}};
    CHECK(instruction == expected);

    CHECK(aos::agent::read_history(world.path, "bob").empty());
    CHECK(aos::agent::read_pending(world.path, "bob").calls.empty());
    CHECK(aos::agent::read_tools(world.path, "bob").size() == 3);
    CHECK(aos::agent::read_status(world.path, "bob").status == "idle");

    CHECK_THROWS_AS(aos::agent::initialize(world.path, "bob"),
                    std::runtime_error);
}

TEST_CASE("agent resolves the containing world and its only agent") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    const auto sub = world.path / "sub";
    std::filesystem::create_directories(sub);

    ScopedUnsetFolder folder_environment;
    ScopedCurrentPath current_path(sub);
    CHECK(aos::agent::resolve_folder() ==
          aos::agent::absolute_folder(world.path));
    CHECK(aos::agent::resolve_name(world.path) == "bob");
    CHECK(aos::agent::resolve_name(world.path, "given") == "given");
}

TEST_CASE("agent name resolution rejects zero or multiple residents") {
    TempWorld world;
    CHECK_THROWS_AS(aos::agent::resolve_name(world.path), std::runtime_error);

    const auto agents = world.path / ".aos" / "agents";
    std::filesystem::create_directories(agents / "alice");
    std::filesystem::create_directories(agents / "bob");
    CHECK_THROWS_AS(aos::agent::resolve_name(world.path), std::runtime_error);
}

TEST_CASE("agent say atomically queues one message file") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    aos::agent::say(world.path, "bob", "第一句");
    aos::agent::say(world.path, "bob", "第二句");

    const auto say = world.path / ".aos" / "agents" / "bob" / "say";
    std::size_t markdown = 0;
    for (const auto &entry : std::filesystem::directory_iterator(say)) {
        CHECK(entry.path().extension() != ".tmp");
        if (entry.path().extension() == ".md") ++markdown;
    }
    CHECK(markdown == 2);
}
