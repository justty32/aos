#include "test_support.hpp"

using namespace aos::loop;
using namespace aos::loop::test;

TEST_CASE("run_turn mirrors agent status into state") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    std::string error;
    REQUIRE(ensure_layout(layout, error));
    REQUIRE(std::filesystem::create_directories(layout.agents_dir + "/bob"));
    const std::string status =
        "{\"status\":\"thinking\",\"detail\":\"working\","
        "\"updated_at\":\"now\",\"turn\":1}\n";
    write_file(layout.agents_dir + "/bob/status.json", status);

    const auto mirrored = mirror_agents(layout);
    REQUIRE(mirrored.contains("bob"));
    CHECK(mirrored.at("bob") == status);

    TurnSummary summary;
    REQUIRE(run_turn(layout, summary, error));
    const aos::wire::State state = read_state(layout);
    CHECK(state.agents.contains("bob"));
}
