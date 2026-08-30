#include <aos/wire.hpp>

#include <catch2/catch_test_macros.hpp>

#include <optional>
#include <string>

TEST_CASE("wire outcome 正常結束與訊號結束都可以 round trip") {
    const aos::wire::Outcome exited{
        .id = "one",
        .exit = 0,
        .signal = std::nullopt,
        .stdout_text = "ok\n",
        .stderr_text = "",
        .started_at = "2026-08-30T00:00:00.000Z",
        .ended_at = "2026-08-30T00:00:01.000Z",
    };
    const aos::wire::Outcome signalled{
        .id = "two",
        .exit = std::nullopt,
        .signal = 9,
        .stdout_text = "",
        .stderr_text = "killed",
        .started_at = "2026-08-30T00:00:00.000Z",
        .ended_at = "2026-08-30T00:00:00.200Z",
    };

    std::string error;
    const std::string exited_text = aos::wire::to_json_text(exited);
    const auto exited_again = aos::wire::parse_outcome(exited_text, error);
    REQUIRE(exited_again.has_value());
    CHECK(exited_again->exit == 0);
    CHECK_FALSE(exited_again->signal.has_value());
    CHECK(exited_text.find("\"signal\": null") != std::string::npos);

    const auto signalled_again = aos::wire::parse_outcome(
        aos::wire::to_json_text(signalled), error);
    REQUIRE(signalled_again.has_value());
    CHECK_FALSE(signalled_again->exit.has_value());
    CHECK(signalled_again->signal == 9);

    const std::string both =
        R"({"id":"a","exit":0,"signal":9,"stdout":"","stderr":"","started_at":"s","ended_at":"e"})";
    const std::string neither =
        R"({"id":"a","exit":null,"signal":null,"stdout":"","stderr":"","started_at":"s","ended_at":"e"})";
    CHECK_FALSE(aos::wire::parse_outcome(both, error).has_value());
    CHECK_FALSE(error.empty());
    CHECK_FALSE(aos::wire::parse_outcome(neither, error).has_value());
    CHECK_FALSE(error.empty());
}
