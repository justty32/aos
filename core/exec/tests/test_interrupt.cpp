#include <aos/exec.hpp>

#include <catch2/catch_test_macros.hpp>

#include <chrono>
#include <vector>

#include <signal.h>

TEST_CASE("interrupt_running 會立即中止尚未收線的行程群組") {
    const std::vector<aos::exec::Spawn> spawns{
        {.argv = {"sleep", "30"}},
    };

    auto running = aos::exec::start_all(spawns);
    REQUIRE(running.size() == 1);
    REQUIRE(running[0].pid > 0);

    const auto started = std::chrono::steady_clock::now();
    CHECK(aos::exec::interrupt_running(SIGKILL) == 1);
    const auto results = aos::exec::wait_all(running);
    const auto elapsed = std::chrono::steady_clock::now() - started;

    REQUIRE(results.size() == 1);
    CHECK(results[0].signal == SIGKILL);
    CHECK(results[0].error.empty());
    CHECK(elapsed < std::chrono::seconds(1));
}
