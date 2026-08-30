#include <aos/agent.hpp>

#include <catch2/catch_test_macros.hpp>

#include <string>
#include <vector>

TEST_CASE("agent argument templates replace args without word splitting") {
    const std::vector<std::string> expanded = aos::agent::expand_argv(
        {"sh", "pre-{args}-post", "{args}", "x{args}y{args}"}, "a b");
    REQUIRE(expanded.size() == 4);
    CHECK(expanded[0] == "sh");
    CHECK(expanded[1] == "pre-a b-post");
    CHECK(expanded[2] == "a b");
    CHECK(expanded[3] == "xa bya b");
}

TEST_CASE("agent extracts the last valid tool call line") {
    const std::vector<aos::agent::Tool> tools = {
        {"sh", "shell", {"sh", "-lc", "{args}"}},
        {"ls", "list", {"ls", "{args}"}}};

    CHECK_FALSE(aos::agent::extract_tool_call("只是純文字", tools));

    const auto plain = aos::agent::extract_tool_call(
        "我來看看。\n{\"tool\":\"ls\",\"args\":\"-la\"}", tools);
    REQUIRE(plain);
    CHECK(plain->tool == "ls");
    CHECK(plain->args == "-la");

    const auto fenced = aos::agent::extract_tool_call(
        "```json\n{\"tool\":\"sh\",\"args\":\"pwd\"}\n```", tools);
    REQUIRE(fenced);
    CHECK(fenced->tool == "sh");

    std::string unknown;
    CHECK_FALSE(aos::agent::extract_tool_call(
        "{\"tool\":\"missing\",\"args\":\"x\"}", tools, &unknown));
    CHECK(unknown == "missing");

    const auto last = aos::agent::extract_tool_call(
        "{\"tool\":\"sh\",\"args\":\"first\"}\n"
        "中間文字\n"
        "{\"tool\":\"ls\",\"args\":\"last\"}",
        tools);
    REQUIRE(last);
    CHECK(last->tool == "ls");
    CHECK(last->args == "last");
}
