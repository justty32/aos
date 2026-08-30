#include <aos/exec.hpp>

#include <catch2/catch_test_macros.hpp>

#include <string>
#include <vector>

TEST_CASE("exec 疊加環境而不移除既有 PATH") {
    const std::vector<aos::exec::Spawn> spawns{
        {.argv = {"sh", "-c", "printf '%s' \"$FOO:$PATH\""},
         .env = {{"FOO", "bar"}}},
    };

    auto running = aos::exec::start_all(spawns);
    const auto results = aos::exec::wait_all(running);

    REQUIRE(results.size() == 1);
    CHECK(results[0].exit == 0);
    CHECK(results[0].stdout_text.starts_with("bar:"));
    CHECK(results[0].stdout_text.size() > std::string("bar:").size());
    CHECK(results[0].error.empty());
}

TEST_CASE("exec 會在指定工作目錄執行") {
    const std::vector<aos::exec::Spawn> spawns{
        {.argv = {"pwd"}, .cwd = "/tmp"},
    };

    auto running = aos::exec::start_all(spawns);
    const auto results = aos::exec::wait_all(running);

    REQUIRE(results.size() == 1);
    CHECK(results[0].exit == 0);
    CHECK(results[0].stdout_text == "/tmp\n");
    CHECK(results[0].error.empty());
}

TEST_CASE("exec 透過暫存檔傳入 stdin") {
    const std::vector<aos::exec::Spawn> spawns{
        {.argv = {"cat"}, .stdin_data = "hello"},
    };

    auto running = aos::exec::start_all(spawns);
    const auto results = aos::exec::wait_all(running);

    REQUIRE(results.size() == 1);
    CHECK(results[0].exit == 0);
    CHECK(results[0].stdout_text == "hello");
    CHECK(results[0].error.empty());
}
