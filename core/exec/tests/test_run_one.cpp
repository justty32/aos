#include <aos/exec.hpp>

#include <catch2/catch_test_macros.hpp>

#include <string>
#include <vector>

TEST_CASE("exec 可以執行單一指令並收回輸出") {
    const std::vector<aos::exec::Spawn> spawns{{.argv = {"echo", "hi"}}};

    auto running = aos::exec::start_all(spawns);
    const auto results = aos::exec::wait_all(running);

    REQUIRE(results.size() == 1);
    CHECK(results[0].exit == 0);
    CHECK(results[0].signal == 0);
    CHECK(results[0].stdout_text == "hi\n");
    CHECK(results[0].stderr_text.empty());
    CHECK(results[0].error.empty());
    CHECK(results[0].pid > 0);
    CHECK_FALSE(results[0].started_at.empty());
    CHECK_FALSE(results[0].ended_at.empty());
}

TEST_CASE("exec 找不到 argv0 時回傳 127") {
    const std::vector<aos::exec::Spawn> spawns{
        {.argv = {"no-such-binary-xyz-aos-test"}},
    };

    auto running = aos::exec::start_all(spawns);
    const auto results = aos::exec::wait_all(running);

    REQUIRE(results.size() == 1);
    CHECK(results[0].exit == 127);
    CHECK(results[0].signal == 0);
    CHECK(results[0].error.empty());
}
