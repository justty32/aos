#include <aos/agent.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <chrono>
#include <filesystem>
#include <fstream>
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

nlohmann::json json_file(const std::filesystem::path &path) {
    std::ifstream input(path);
    nlohmann::json value;
    input >> value;
    return value;
}

}  // namespace

TEST_CASE("agent init creates its complete layout and initial delivery") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob", "沉著的測試員。 ");
    const auto aos = world.path / ".aos";
    const auto agent = aos / "agents" / "bob";

    CHECK(std::filesystem::is_directory(aos / "inbox"));
    CHECK(std::filesystem::is_directory(agent / "say"));
    for (const char *name : {"persona.md", "history.json", "status.json",
                             "log.md", "tools.json", "pending.json"}) {
        CHECK(std::filesystem::is_regular_file(agent / name));
    }
    CHECK(std::filesystem::is_regular_file(aos / "turn"));
    CHECK(std::filesystem::is_regular_file(aos / "state.json"));

    std::vector<std::filesystem::path> deliveries;
    for (const auto &entry : std::filesystem::directory_iterator(aos / "inbox")) {
        if (entry.path().extension() == ".json") deliveries.push_back(entry.path());
    }
    REQUIRE(deliveries.size() == 1);
    const nlohmann::json instruction = json_file(deliveries.front());
    CHECK(instruction["id"] == "agent-bob-0");
    CHECK(instruction["argv"] == nlohmann::json::array(
                                     {"aos", "agent", "step",
                                      aos::agent::absolute_folder(world.path).string(),
                                      "bob"}));

    CHECK(aos::agent::read_history(world.path, "bob").empty());
    CHECK(aos::agent::read_pending(world.path, "bob").calls.empty());
    CHECK(aos::agent::read_tools(world.path, "bob").size() == 3);
    CHECK(aos::agent::read_status(world.path, "bob").status == "idle");
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
