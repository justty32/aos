#include "test_support.hpp"

#include <chrono>

using namespace aos::loop;
using namespace aos::loop::test;

TEST_CASE("run_turn starts a batch in parallel") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    deliver_command(layout, command("one", {"sh", "-c", "sleep 1"}));
    deliver_command(layout, command("two", {"sh", "-c", "sleep 1"}));
    deliver_command(layout, command("three", {"sh", "-c", "sleep 1"}));

    const auto started = std::chrono::steady_clock::now();
    TurnSummary summary;
    std::string error;
    REQUIRE(run_turn(layout, summary, error));
    const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - started);

    CHECK(summary.count == 3);
    CHECK(elapsed.count() < 2000);
}
