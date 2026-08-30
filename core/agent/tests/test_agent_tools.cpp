#include <aos/agent.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <unistd.h>

namespace {

class TempWorld {
public:
    TempWorld() {
        const auto stamp = std::chrono::steady_clock::now()
                               .time_since_epoch()
                               .count();
        path = std::filesystem::temp_directory_path() /
               ("aos-agent-tools-" + std::to_string(getpid()) + "-" +
                std::to_string(stamp));
        std::filesystem::create_directories(path);
    }
    ~TempWorld() { std::filesystem::remove_all(path); }
    std::filesystem::path path;
};

aos::tool::Spec spec(std::string name, std::string shape,
                     std::vector<std::string> argv) {
    aos::tool::Spec value;
    value.name = std::move(name);
    value.argv = std::move(argv);
    value.description = "測試工具";
    value.args = std::move(shape);
    return value;
}

void write_json(const std::filesystem::path &path,
                const nlohmann::json &value) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path);
    output << value.dump();
}

}  // namespace

TEST_CASE("agent expands argv for all registered argument shapes") {
    const auto list = aos::agent::expand_argv(
        spec("ls", "list", {"ls"}),
        aos::agent::ToolCall{"ls", "list", {"-la", "."}, {}});
    CHECK(list == std::vector<std::string>{"ls", "-la", "."});

    const auto shell = aos::agent::expand_argv(
        spec("sh", "string", {"sh", "-lc", "{args}"}),
        aos::agent::ToolCall{"sh", "string", {}, "echo hi"});
    CHECK(shell == std::vector<std::string>{"sh", "-lc", "echo hi"});

    const auto appended = aos::agent::expand_argv(
        spec("runner", "string", {"runner", "--expression"}),
        aos::agent::ToolCall{"runner", "string", {}, "a b"});
    CHECK(appended ==
          std::vector<std::string>{"runner", "--expression", "a b"});

    const auto none =
        aos::agent::expand_argv(spec("clock", "none", {"clock", "now"}),
                                aos::agent::ToolCall{"clock", "none", {}, {}});
    CHECK(none == std::vector<std::string>{"clock", "now"});
}

TEST_CASE("agent extracts and validates tool calls by registered shape") {
    const std::vector<aos::tool::Spec> tools = {
        spec("ls", "list", {"ls"}),
        spec("sh", "string", {"sh", "-lc", "{args}"}),
        spec("clock", "none", {"clock"})};

    const auto plain = aos::agent::extract_tool_call("只是純文字", tools);
    CHECK_FALSE(plain.saw_json);
    CHECK_FALSE(plain.call);
    CHECK_FALSE(plain.error);

    const auto list = aos::agent::extract_tool_call(
        "我來看看。\n{\"tool\":\"ls\",\"args\":[\"-la\",\".\"]}", tools);
    REQUIRE(list.saw_json);
    REQUIRE(list.call);
    CHECK(list.call->shape == "list");
    CHECK(list.call->args == std::vector<std::string>{"-la", "."});

    const auto string = aos::agent::extract_tool_call(
        "{\"tool\":\"sh\",\"args\":\"echo hi\"}", tools);
    REQUIRE(string.call);
    CHECK(string.call->shape == "string");
    CHECK(string.call->args_text == "echo hi");

    const auto last =
        aos::agent::extract_tool_call("{\"tool\":\"sh\",\"args\":\"first\"}\n"
                                      "中間文字\n"
                                      "{\"tool\":\"ls\",\"args\":[\"last\"]}",
                                      tools);
    REQUIRE(last.call);
    CHECK(last.call->tool == "ls");
    CHECK(last.call->args == std::vector<std::string>{"last"});

    const auto unknown = aos::agent::extract_tool_call(
        "{\"tool\":\"missing\",\"args\":[]}", tools);
    REQUIRE(unknown.saw_json);
    REQUIRE(unknown.error);
    CHECK(unknown.error->type == "unknown_tool");
    CHECK(unknown.error->tool == "missing");

    const auto invalid = aos::agent::extract_tool_call(
        "{\"tool\":\"ls\",\"args\":\"-la\"}", tools);
    REQUIRE(invalid.error);
    CHECK(invalid.error->type == "invalid_args");

    const auto none = aos::agent::extract_tool_call(
        "{\"tool\":\"clock\",\"args\":[]}", tools);
    REQUIRE(none.call);
    CHECK(none.call->shape == "none");
}

TEST_CASE("agent intersects the world registry with its optional whitelist") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob");
    const auto whitelist =
        world.path / ".aos" / "agents" / "bob" / "tools.json";

    REQUIRE_FALSE(std::filesystem::exists(whitelist));
    auto tools = aos::agent::read_tools(world.path, "bob");
    REQUIRE(tools.size() == 3);
    CHECK(tools[0].name == "cat");
    CHECK(tools[1].name == "ls");
    CHECK(tools[2].name == "sh");

    write_json(whitelist, nlohmann::json::array({"ls"}));
    tools = aos::agent::read_tools(world.path, "bob");
    REQUIRE(tools.size() == 1);
    CHECK(tools[0].name == "ls");

    write_json(whitelist, nlohmann::json::array());
    CHECK(aos::agent::read_tools(world.path, "bob").empty());

    write_json(whitelist, {{"tools", {{{"name", "cat"}}, "missing", "sh"}}});
    tools = aos::agent::read_tools(world.path, "bob");
    REQUIRE(tools.size() == 2);
    CHECK(tools[0].name == "cat");
    CHECK(tools[1].name == "sh");
}
