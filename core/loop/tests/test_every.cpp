#include "test_support.hpp"

using namespace aos::loop;
using namespace aos::loop::test;

TEST_CASE("every instruction runs once in every turn and stays published") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    std::string error;
    REQUIRE(ensure_layout(layout, error));
    write_file(
        layout.every + "/tick.json",
        aos::wire::to_json_text(
            command("ignored", {"sh", "-c", "echo tick"})));

    for (std::uint64_t turn = 1; turn <= 3; ++turn) {
        TurnSummary summary;
        REQUIRE(run_turn(layout, summary, error));
        CHECK(summary.turn == turn);
        CHECK(summary.count == 1);
        CHECK(std::filesystem::exists(
            insts_dir(layout, turn) + "/tick-" + std::to_string(turn) +
            ".json"));
        const std::string outcome_path =
            out_dir(layout, turn) + "/tick-" + std::to_string(turn) +
            ".json";
        REQUIRE(std::filesystem::exists(outcome_path));
        const aos::wire::Outcome outcome = read_outcome(outcome_path);
        REQUIRE(outcome.exit.has_value());
        CHECK(*outcome.exit == 0);
        CHECK(std::filesystem::exists(layout.every + "/tick.json"));
        CHECK(std::filesystem::is_empty(layout.inbox));
    }
}

TEST_CASE("every instruction id is replaced by stem and turn") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    std::string error;
    REQUIRE(ensure_layout(layout, error));
    write_file(layout.every + "/x.json",
               aos::wire::to_json_text(command("whatever", {"true"})));

    TurnSummary summary;
    REQUIRE(run_turn(layout, summary, error));

    const std::string instruction_path = insts_dir(layout, 1) + "/x-1.json";
    REQUIRE(std::filesystem::exists(instruction_path));
    auto instruction = aos::wire::parse_inst(read_file(instruction_path),
                                             "fallback", error);
    REQUIRE(instruction.has_value());
    CHECK(instruction->id == "x-1");
    CHECK(std::filesystem::exists(out_dir(layout, 1) + "/x-1.json"));
}

TEST_CASE("inbox and every instructions run in the same turn") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    std::string error;
    REQUIRE(ensure_layout(layout, error));
    deliver_command(layout, command("once", {"true"}));
    write_file(layout.every + "/again.json",
               aos::wire::to_json_text(command("ignored", {"true"})));

    TurnSummary summary;
    REQUIRE(run_turn(layout, summary, error));
    CHECK(summary.count == 2);
    CHECK(std::filesystem::exists(out_dir(layout, 1) + "/once.json"));
    CHECK(std::filesystem::exists(out_dir(layout, 1) + "/again-1.json"));
    CHECK_FALSE(std::filesystem::exists(layout.inbox + "/once.json"));
    CHECK(std::filesystem::exists(layout.every + "/again.json"));
}

TEST_CASE("every due uses the last delivered timestamp") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    std::string error;

    CHECK(every_due(layout, "slow", 500, 1000));
    REQUIRE(mark_every_delivered(layout, "slow", 1000, error));
    CHECK_FALSE(every_due(layout, "slow", 500, 1400));
    CHECK(every_due(layout, "slow", 500, 1500));
    CHECK(read_file(layout.every + "/.last/slow") == "1000\n");
}

TEST_CASE("every ms skips turns until its interval is due") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    std::string error;
    REQUIRE(ensure_layout(layout, error));
    write_file(layout.every + "/slow.json",
               R"({"argv":["true"],"every_ms":600000})");

    TurnSummary first;
    REQUIRE(run_turn(layout, first, error));
    CHECK(first.count == 1);
    CHECK(first.every_count == 1);
    CHECK(std::filesystem::exists(insts_dir(layout, 1) + "/slow-1.json"));
    CHECK_FALSE(std::filesystem::exists(insts_dir(layout, 1) + "/.last"));

    for (std::uint64_t turn = 2; turn <= 3; ++turn) {
        TurnSummary summary;
        REQUIRE(run_turn(layout, summary, error));
        CHECK(summary.turn == turn);
        CHECK(summary.count == 0);
        CHECK(summary.every_count == 0);
        CHECK_FALSE(std::filesystem::exists(
            layout.aos + "/batch/" + std::to_string(turn)));
    }
    CHECK(std::filesystem::exists(layout.every + "/slow.json"));
}

TEST_CASE("every files keep independent delivery intervals") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    std::string error;
    REQUIRE(ensure_layout(layout, error));
    write_file(layout.every + "/slow.json",
               R"({"argv":["true"],"every_ms":600000})");
    write_file(layout.every + "/fast.json", R"({"argv":["true"]})");

    TurnSummary first;
    REQUIRE(run_turn(layout, first, error));
    CHECK(first.count == 2);
    CHECK(first.every_count == 2);

    TurnSummary second;
    REQUIRE(run_turn(layout, second, error));
    CHECK(second.count == 1);
    CHECK(second.every_count == 1);
    CHECK(std::filesystem::exists(insts_dir(layout, 2) + "/fast-2.json"));
    CHECK_FALSE(std::filesystem::exists(insts_dir(layout, 2) + "/slow-2.json"));
}
