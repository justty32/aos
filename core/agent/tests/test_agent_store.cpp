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

extern "C" int aos_say_cli_main(int argc, char *argv[]);

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

class ScopedFolder {
public:
    explicit ScopedFolder(const std::filesystem::path &path) {
        if (const char *value = std::getenv("AOS_FOLDER")) original_ = value;
        REQUIRE(setenv("AOS_FOLDER", path.c_str(), 1) == 0);
    }
    ~ScopedFolder() {
        if (original_) setenv("AOS_FOLDER", original_->c_str(), 1);
        else unsetenv("AOS_FOLDER");
    }

private:
    std::optional<std::string> original_;
};

class ScopedHome {
public:
    explicit ScopedHome(const std::filesystem::path &path) {
        if (const char *value = std::getenv("HOME")) original_ = value;
        REQUIRE(setenv("HOME", path.c_str(), 1) == 0);
    }
    ~ScopedHome() {
        if (original_) setenv("HOME", original_->c_str(), 1);
        else unsetenv("HOME");
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
                             "log.md", "pending.json"}) {
        CHECK(std::filesystem::is_regular_file(agent / name));
    }
    CHECK_FALSE(std::filesystem::exists(agent / "tools.json"));
    for (const char *name : {"cat.json", "ls.json", "sh.json"}) {
        CHECK(std::filesystem::is_regular_file(aos / "tools" / name));
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

TEST_CASE("agent reads legacy string pending args as a JSON string value") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    const auto path = world.path / ".aos" / "agents" / "bob" / "pending.json";
    std::ofstream output(path, std::ios::trunc);
    output
        << R"({"turn":3,"calls":[{"id":"old","tool":"sh","args":"echo hi"}]})";
    output.close();

    const aos::agent::Pending pending =
        aos::agent::read_pending(world.path, "bob");
    REQUIRE(pending.calls.size() == 1);
    CHECK(pending.calls[0].args_json == "\"echo hi\"");
}

TEST_CASE("top-level say can deliver through a world contact") {
    TempWorld source;
    TempWorld target;
    TempWorld home;
    ScopedHome scoped_home(home.path);
    aos::agent::initialize(source.path, "alice");
    aos::agent::initialize(target.path, "worker");
    aos::tool::add_contact(
        source.path,
        aos::tool::Contact{"bob", target.path.string(), {}, "測試聯絡人"});
    ScopedFolder current_world(source.path);

    char program[] = "aos say";
    char option[] = "--to";
    char contact[] = "bob";
    char greeting[] = "嗨";
    char *argv[] = {program, option, contact, greeting};
    CHECK(aos_say_cli_main(4, argv) == 0);

    const auto say = target.path / ".aos" / "agents" / "worker" / "say";
    std::vector<std::filesystem::path> messages;
    for (const auto &entry : std::filesystem::directory_iterator(say)) {
        if (entry.is_regular_file() && entry.path().extension() == ".md") {
            messages.push_back(entry.path());
        }
    }
    REQUIRE(messages.size() == 1);
    std::ifstream input(messages.front());
    const std::string text{std::istreambuf_iterator<char>(input),
                           std::istreambuf_iterator<char>()};
    const std::string prefix =
        "from: " + aos::agent::absolute_folder(source.path).string() +
        "\n\n";
    CHECK(text.starts_with(prefix));
    CHECK(text.ends_with("嗨"));
}

TEST_CASE("top-level say delivers to the synthetic user contact and drains") {
    TempWorld source;
    TempWorld home;
    ScopedHome scoped_home(home.path);
    aos::agent::initialize(source.path, "alice");
    ScopedFolder current_world(source.path);

    char program[] = "aos say";
    char option[] = "--to";
    char contact[] = "~";
    char report[] = "回報完成";
    char *argv[] = {program, option, contact, report};
    CHECK(aos_say_cli_main(4, argv) == 0);

    const auto say = home.path / ".aos" / "say";
    std::vector<std::filesystem::path> messages;
    for (const auto &entry : std::filesystem::directory_iterator(say)) {
        if (entry.is_regular_file() && entry.path().extension() == ".md") {
            messages.push_back(entry.path());
        }
    }
    REQUIRE(messages.size() == 1);
    std::ifstream input(messages.front());
    const std::string text{std::istreambuf_iterator<char>(input),
                           std::istreambuf_iterator<char>()};
    CHECK(text.find("from: " +
                    aos::agent::absolute_folder(source.path).string()) !=
          std::string::npos);
    CHECK(text.find("回報完成") != std::string::npos);

    CHECK(aos::agent::drain_user_say() == 1);
    CHECK(aos::agent::read_user_log().find("回報完成") != std::string::npos);
    CHECK(std::filesystem::is_empty(say));
}

TEST_CASE("user folder is HOME and say sender falls back to it") {
    TempWorld sandbox;
    const std::filesystem::path home = sandbox.path / "home";
    const std::filesystem::path outside = sandbox.path / "outside";
    std::filesystem::create_directories(home);
    std::filesystem::create_directories(outside);
    ScopedHome scoped_home(home);
    ScopedUnsetFolder folder_environment;
    ScopedCurrentPath current_path(outside);

    const std::filesystem::path expected =
        aos::agent::absolute_folder(home);
    CHECK(aos::agent::user_folder() == expected);
    CHECK(aos::agent::is_user_folder(home));
    CHECK_FALSE(aos::agent::is_user_folder(outside));
    CHECK(aos::agent::say_from() == expected);
}
