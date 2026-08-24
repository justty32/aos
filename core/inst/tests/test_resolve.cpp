#include <aos/inst.hpp>

#include <catch2/catch_test_macros.hpp>

#include <string>

namespace {

aos::inst_t parse(const std::string &document) {
    aos::inst_t inst;
    REQUIRE(aos::read_one(document.data(), document.size(), inst) ==
            aos::InstState::Ok);
    return inst;
}

aos::ResolveContext context() {
    aos::ResolveContext value;
    value.environment = {
        {"ARG", "argument"}, {"IN", "input"}, {"OUT", "output"},
        {"ERR", "error"}, {"EXIT", "status"}, {"CWD", "work"},
        {"VALUE", "env-value"},
    };
    value.base_path = "/world";
    return value;
}

}  // namespace

TEST_CASE("environment directives resolve in every string value position") {
    aos::inst_t inst = parse(
        R"({"argv":["command",{"$env":"ARG"}],"stdin":{"$env":"IN"},"stdout":{"$env":"OUT"},"stderr":{"$env":"ERR"},"exit":{"$env":"EXIT"},"cwd":{"$env":"CWD"},"env":{"KEY":{"$env":"VALUE"}}})");
    aos::ResolveResult result;

    REQUIRE(aos::resolve(inst, context(), result) == aos::ResolveState::Ok);
    CHECK(inst.argv == std::vector<std::string>{"command", "argument"});
    CHECK(inst.stdin_path == "input");
    CHECK(inst.stdout_path == "output");
    CHECK(inst.stderr_path == "error");
    CHECK_FALSE(inst.stderr_merge);
    CHECK(inst.exit_path == "status");
    CHECK(inst.cwd == "work");
    CHECK(inst.env == std::map<std::string, std::string>{{"KEY", "env-value"}});
    CHECK(inst.pending_directives.empty());
}

TEST_CASE("missing environment variable reports its variable and position") {
    aos::inst_t inst = parse(
        R"({"argv":["command",{"$env":"MISSING"}]})");
    aos::ResolveResult result;

    CHECK(aos::resolve(inst, context(), result) ==
          aos::ResolveState::EnvironmentVariableMissing);
    CHECK(result.variable == "MISSING");
    CHECK(result.field == aos::DirectiveField::Argv);
    CHECK(result.argv_index == 1);
    CHECK(inst.pending_directives.size() == 1);
}

TEST_CASE("empty resolved argv zero is rejected after resolution") {
    aos::inst_t inst = parse(R"({"argv":[{"$env":"EMPTY"}]})");
    aos::ResolveContext ctx;
    ctx.environment["EMPTY"] = "";
    aos::ResolveResult result;

    CHECK(aos::resolve(inst, ctx, result) ==
          aos::ResolveState::ValidationFailed);
    CHECK(result.validation_state == aos::InstState::EmptyArgv);
    CHECK(inst.pending_directives.size() == 1);
}

TEST_CASE("unresolved environment directives round trip without loss") {
    const std::string document =
        R"({"argv":["command",{"$env":"ARG"}],"stderr":{"$env":"ERR"},"env":{"KEY":{"$env":"VALUE"}}})";
    aos::inst_t inst = parse(document);
    std::string encoded;

    REQUIRE(aos::write_one(inst, encoded) == aos::InstState::Ok);
    CHECK(encoded == document + "\n");
}

TEST_CASE("stderr accepts literal merge and environment directive forms") {
    aos::inst_t literal = parse(R"({"argv":["x"],"stderr":"error"})");
    aos::inst_t merge = parse(
        R"({"argv":["x"],"stderr":{"$opt":"merge"}})");
    aos::inst_t environment = parse(
        R"({"argv":["x"],"stderr":{"$env":"ERR"}})");
    aos::ResolveResult result;

    CHECK(literal.stderr_path == "error");
    CHECK(merge.stderr_merge);
    REQUIRE(aos::resolve(environment, context(), result) ==
            aos::ResolveState::Ok);
    CHECK(environment.stderr_path == "error");
    CHECK_FALSE(environment.stderr_merge);
}

TEST_CASE("directives remain forbidden in non string value positions") {
    aos::inst_t inst;
    const std::string timeout =
        R"({"argv":["x"],"timeout_ms":{"$env":"TIMEOUT"}})";
    CHECK(aos::read_one(timeout.data(), timeout.size(), inst) ==
          aos::InstState::FieldTypeMismatch);

    const std::string env_not_an_object =
        R"({"argv":["x"],"env":[{"$env":"ENV_KEY"}]})";
    CHECK(aos::read_one(env_not_an_object.data(), env_not_an_object.size(),
                        inst) == aos::InstState::FieldTypeMismatch);
}

TEST_CASE("capture environment keeps empty values and explicit base path") {
    const char *values[] = {"A=one", "EMPTY=", nullptr};
    aos::ResolveContext ctx;

    REQUIRE(aos::capture_environment(values, "/world", ctx) ==
            aos::ResolveState::Ok);
    CHECK(ctx.environment.at("A") == "one");
    CHECK(ctx.environment.at("EMPTY").empty());
    CHECK(ctx.base_path == "/world");
}
