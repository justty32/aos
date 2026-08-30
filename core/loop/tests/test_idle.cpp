#include "test_support.hpp"

using namespace aos::loop;
using namespace aos::loop::test;

TEST_CASE("idle turn advances without creating a batch directory") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    TurnSummary summary;
    std::string error;

    REQUIRE(run_turn(layout, summary, error));
    CHECK(summary.turn == 1);
    CHECK(summary.count == 0);
    CHECK_FALSE(std::filesystem::exists(layout.aos + "/batch/1"));
    CHECK(read_turn(layout) == 2);

    const aos::wire::State state = read_state(layout);
    CHECK(state.turn == 1);
    CHECK(state.phase == "idle");
    CHECK(state.running.empty());
}
