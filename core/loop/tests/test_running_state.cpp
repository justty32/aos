#include "test_support.hpp"

using namespace aos::loop;
using namespace aos::loop::test;

TEST_CASE("commands can observe the running state before wait_all") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    const std::string snapshot =
        "while ! grep -q '\"phase\": \"running\"' "
        "\"$AOS_FOLDER/.aos/state.json\" 2>/dev/null; do :; done; "
        "cp \"$AOS_FOLDER/.aos/state.json\" \"$AOS_FOLDER/snapshot.json\"";
    deliver_command(layout, command("snapshot", {"sh", "-c", snapshot}));
    deliver_command(layout, command("peer", {"sh", "-c", "printf peer"}));

    TurnSummary summary;
    std::string error;
    REQUIRE(run_turn(layout, summary, error));

    auto observed = aos::wire::parse_state(
        read_file(dir.path + "/snapshot.json"), error);
    REQUIRE(observed.has_value());
    CHECK(observed->phase == "running");
    REQUIRE(observed->running.size() == 2);
    for (const auto &entry : observed->running) {
        CHECK(entry.pid > 0);
        CHECK(entry.status == "running");
    }

    const aos::wire::State final_state = read_state(layout);
    CHECK(final_state.phase == "idle");
    REQUIRE(final_state.running.size() == 2);
    for (const auto &entry : final_state.running) {
        CHECK(entry.status == "done");
    }
}
