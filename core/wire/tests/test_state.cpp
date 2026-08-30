#include <aos/wire.hpp>

#include <catch2/catch_test_macros.hpp>

#include <optional>
#include <string>

TEST_CASE("wire state 鏡射 agent JSON 並把未知 pid 寫成 null") {
    aos::wire::State state;
    state.turn = 7;
    state.phase = "running";
    state.running.push_back({
        .id = "agent-bob-7",
        .argv0 = "aos",
        .pid = -1,
        .started_at = "2026-08-30T00:00:00.000Z",
        .status = "running",
        .exit = std::nullopt,
    });
    state.agents["bob"] =
        R"({"status":"thinking","nested":{"items":[1,true,null]}})";

    const std::string text = aos::wire::to_json_text(state);
    std::string error;
    const auto parsed = aos::wire::parse_state(text, error);

    REQUIRE(parsed.has_value());
    CHECK(error.empty());
    CHECK(parsed->turn == 7);
    CHECK(parsed->phase == "running");
    REQUIRE(parsed->running.size() == 1);
    CHECK(parsed->running[0].pid == -1);
    CHECK_FALSE(parsed->running[0].exit.has_value());
    REQUIRE(parsed->agents.contains("bob"));

    const auto reparsed = aos::wire::parse_state(
        aos::wire::to_json_text(*parsed), error);
    REQUIRE(reparsed.has_value());
    CHECK(reparsed->agents.at("bob") == parsed->agents.at("bob"));
    CHECK(text.find("\"pid\": null") != std::string::npos);

    aos::wire::State invalid_agent;
    invalid_agent.agents["broken"] = "{not json";
    const std::string invalid_text = aos::wire::to_json_text(invalid_agent);
    CHECK(invalid_text.find("\"broken\": null") != std::string::npos);
}
