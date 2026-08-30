#include "test_support.hpp"

using namespace aos::loop;
using namespace aos::loop::test;

TEST_CASE("run_turn moves and executes every delivered instruction") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    deliver_command(layout, command("first", {"sh", "-c", "printf first"}));
    deliver_command(layout, command("second", {"sh", "-c", "printf second"}));

    TurnSummary summary;
    std::string error;
    REQUIRE(run_turn(layout, summary, error));
    CHECK(summary.turn == 1);
    CHECK(summary.count == 2);
    CHECK(std::filesystem::is_empty(layout.inbox));
    CHECK(json_files(insts_dir(layout, 1)).size() == 2);
    CHECK(json_files(out_dir(layout, 1)).size() == 2);
    CHECK(read_turn(layout) == 2);

    const auto first = read_outcome(out_dir(layout, 1) + "/first.json");
    const auto second = read_outcome(out_dir(layout, 1) + "/second.json");
    REQUIRE(first.exit.has_value());
    REQUIRE(second.exit.has_value());
    CHECK(*first.exit == 0);
    CHECK(*second.exit == 0);
    CHECK(first.stdout_text == "first");
    CHECK(second.stdout_text == "second");
}
