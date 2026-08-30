#include <aos/agent.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <unistd.h>
#include <vector>

namespace {

class TempWorld {
  public:
    TempWorld() {
        const auto stamp =
            std::chrono::steady_clock::now().time_since_epoch().count();
        path = std::filesystem::temp_directory_path() /
               ("aos-agent-tools-" + std::to_string(getpid()) + "-" +
                std::to_string(stamp));
        std::filesystem::create_directories(path);
    }
    ~TempWorld() {
        std::filesystem::remove_all(path);
    }
    std::filesystem::path path;
};

class ScopedUnsetHome {
  public:
    ScopedUnsetHome() {
        if (const char *value = std::getenv("HOME")) original_ = value;
        if (const char *value = std::getenv("AOS_HOME"))
            original_aos_home_ = value;
        REQUIRE(unsetenv("HOME") == 0);
        REQUIRE(setenv("AOS_HOME",
                       std::filesystem::temp_directory_path().c_str(), 1) == 0);
    }
    ~ScopedUnsetHome() {
        if (original_)
            setenv("HOME", original_->c_str(), 1);
        else
            unsetenv("HOME");
        if (original_aos_home_)
            setenv("AOS_HOME", original_aos_home_->c_str(), 1);
        else
            unsetenv("AOS_HOME");
    }

  private:
    std::optional<std::string> original_;
    std::optional<std::string> original_aos_home_;
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
    REQUIRE(tools.size() == 4);
    CHECK(tools[0].name == "cat");
    CHECK(tools[1].name == "ls");
    CHECK(tools[2].name == "say");
    CHECK(tools[3].name == "sh");

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

TEST_CASE("agent system prompt lists contacts and explains available say") {
    TempWorld world;
    aos::agent::initialize(world.path, "bob", "負責協調。", {});
    aos::tool::add_contact(world.path,
                           {"w1", "../w1", "", "負責實機測試\n與驗收"});
    aos::agent::say(world.path, "bob", "請列出聯絡人");
    std::string with_say;
    REQUIRE(
        aos::agent::step(world.path, "bob",
                         [&](const std::vector<aos::agent::Message> &messages) {
                             with_say = messages.front().content;
                             return "已看到。";
                         }) == 0);
    CHECK(with_say.find("你可以聯絡這些人") != std::string::npos);
    CHECK(with_say.find("- w1 — 負責實機測試 與驗收（../w1）") !=
          std::string::npos);
    CHECK(with_say.find(
              "{\"tool\":\"say\",\"args\":[\"收件人名字\",\"訊息內容\"]}") !=
          std::string::npos);

    write_json(world.path / ".aos" / "agents" / "bob" / "tools.json",
               nlohmann::json::array({"ls"}));
    aos::agent::say(world.path, "bob", "再看一次");
    std::string no_say;
    REQUIRE(
        aos::agent::step(world.path, "bob",
                         [&](const std::vector<aos::agent::Message> &messages) {
                             no_say = messages.front().content;
                             return "仍看得到。";
                         }) == 0);
    CHECK(no_say.find("- w1 — 負責實機測試 與驗收（../w1）") !=
          std::string::npos);
    CHECK(no_say.find("{\"tool\":\"say\"") == std::string::npos);
}

TEST_CASE("agent system prompt omits an empty contact section") {
    ScopedUnsetHome no_home;
    TempWorld world;
    aos::agent::initialize(world.path, "bob", "保持簡潔。", {});
    aos::agent::say(world.path, "bob", "有人嗎");
    std::string prompt;
    REQUIRE(
        aos::agent::step(world.path, "bob",
                         [&](const std::vector<aos::agent::Message> &messages) {
                             prompt = messages.front().content;
                             return "在。";
                         }) == 0);
    CHECK(prompt.find("你可以聯絡這些人") == std::string::npos);
}
