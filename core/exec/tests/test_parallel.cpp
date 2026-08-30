#include <aos/exec.hpp>

#include <catch2/catch_test_macros.hpp>

#include <chrono>
#include <vector>

TEST_CASE("exec 會先啟動整批再統一等待") {
    const std::vector<aos::exec::Spawn> spawns{
        {.argv = {"sh", "-c", "sleep 1"}},
        {.argv = {"sh", "-c", "sleep 1"}},
        {.argv = {"sh", "-c", "sleep 1"}},
    };

    const auto started = std::chrono::steady_clock::now();
    auto running = aos::exec::start_all(spawns);
    const auto results = aos::exec::wait_all(running);
    const auto elapsed = std::chrono::steady_clock::now() - started;

    REQUIRE(results.size() == 3);
    for (const auto &result : results) {
        CHECK(result.exit == 0);
        CHECK(result.signal == 0);
        CHECK(result.error.empty());
    }
    CHECK(elapsed < std::chrono::seconds(2));
}
