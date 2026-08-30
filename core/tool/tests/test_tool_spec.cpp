#include <aos/tool.hpp>

#include <catch2/catch_test_macros.hpp>

namespace {

void check_equal(const aos::tool::Spec &left, const aos::tool::Spec &right) {
    CHECK(left.name == right.name);
    CHECK(left.argv == right.argv);
    CHECK(left.description == right.description);
    CHECK(left.args == right.args);
    CHECK(left.stdin_mode == right.stdin_mode);
    CHECK(left.cwd == right.cwd);
    CHECK(left.timeout_ms == right.timeout_ms);
    CHECK(left.source == right.source);
    CHECK(left.lifecycle == right.lifecycle);
    CHECK(left.state == right.state);
    CHECK(left.guarantee == right.guarantee);
    CHECK(left.interruptible == right.interruptible);
    CHECK(left.predictability == right.predictability);
    CHECK(left.stage == right.stage);
    CHECK(left.network == right.network);
    CHECK(left.network_declared == right.network_declared);
    CHECK(left.env_allow == right.env_allow);
}

}  // namespace

TEST_CASE("tool spec JSON round trip preserves all declared fields") {
    aos::tool::Spec spec;
    spec.name = "deploy.v2";
    spec.argv = {"runner", "--fixed"};
    spec.description = "部署測試服務。";
    spec.args = "string";
    spec.stdin_mode = "text";
    spec.cwd = "work";
    spec.timeout_ms = 42;
    spec.source = "metainfo";
    spec.lifecycle = "stable";
    spec.state = "writes";
    spec.guarantee = "at-most-once";
    spec.interruptible = "yes";
    spec.predictability = "medium";
    spec.stage = "deploy";
    spec.network = false;
    spec.network_declared = true;
    spec.env_allow = {"PATH", "TOKEN"};

    check_equal(aos::tool::parse_spec(aos::tool::spec_to_json(spec)), spec);
}

TEST_CASE("tool spec rejects missing and invalid required data") {
    CHECK_THROWS(aos::tool::parse_spec(R"({"name":"x","argv":["x"]})"));
    CHECK_THROWS(aos::tool::parse_spec(
        R"({"name":"x","description":"x"})"));
    CHECK_THROWS(aos::tool::parse_spec(
        R"({"name":"x","argv":[],"description":"x"})"));
    CHECK_THROWS(aos::tool::parse_spec(
        R"({"name":"x","argv":["x"],"description":"x","args":"map"})"));
}

TEST_CASE("tool spec ignores unknown fields and supplies defaults") {
    const aos::tool::Spec spec = aos::tool::parse_spec(
        R"({"name":"x","argv":["x"],"description":"說明","future":7})");
    CHECK(spec.args == "list");
    CHECK(spec.stdin_mode == "none");
    CHECK(spec.source == "manual");
    CHECK_FALSE(spec.network_declared);
}
