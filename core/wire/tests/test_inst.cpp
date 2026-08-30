#include <aos/wire.hpp>

#include <catch2/catch_test_macros.hpp>

#include <string>

TEST_CASE("wire 解析最小 instruction 並採用預設 id") {
    std::string error = "舊錯誤";
    const auto inst = aos::wire::parse_inst(
        R"({"argv":["echo","hi"]})", "a", error);

    REQUIRE(inst.has_value());
    CHECK(error.empty());
    CHECK(inst->id == "a");
    REQUIRE(inst->argv.size() == 2);
    CHECK(inst->argv[0] == "echo");
    CHECK(inst->argv[1] == "hi");
    CHECK(inst->timeout_ms == 0);
}

TEST_CASE("wire instruction 完整欄位可以 round trip") {
    aos::wire::Inst source;
    source.id = "job-1";
    source.argv = {"sh", "-c", "cat"};
    source.env = {{"FOO", "bar"}};
    source.cwd = "work";
    source.stdin_data = "hello";
    source.timeout_ms = 250;

    const std::string text = aos::wire::to_json_text(source);
    std::string error;
    const auto parsed = aos::wire::parse_inst(text, "unused", error);

    REQUIRE(parsed.has_value());
    CHECK(error.empty());
    CHECK(parsed->id == source.id);
    CHECK(parsed->argv == source.argv);
    CHECK(parsed->env == source.env);
    CHECK(parsed->cwd == source.cwd);
    CHECK(parsed->stdin_data == source.stdin_data);
    CHECK(parsed->timeout_ms == source.timeout_ms);
    CHECK(text.back() == '\n');
    CHECK(text.find("\n  \"argv\"") != std::string::npos);
}
