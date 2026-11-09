// exec_timeout.cpp：執行器的 Catch2 測試（搬自 aos-v1 的 core/exec/tests/test_timeout.cpp，11-04 在 c90f86178 刪掉前的版本）。
#include <aos/exec.hpp>

#include <catch2/catch_test_macros.hpp>

#include <chrono>
#include <vector>

TEST_CASE("exec 逾時會用 SIGKILL 收掉整個行程群組") {
    const std::vector<aos::exec::Spawn> spawns{
        {.argv = {"sh", "-c", "sleep 5"}, .timeout_ms = 200},
        {.argv = {"sh", "-c", "sleep 30 & wait"}, .timeout_ms = 200},
    };

    const auto started = std::chrono::steady_clock::now();
    auto running = aos::exec::start_all(spawns);
    const auto results = aos::exec::wait_all(running);
    const auto elapsed = std::chrono::steady_clock::now() - started;

    REQUIRE(results.size() == 2);
    for (const auto &result : results) {
        CHECK(result.exit == 0);
        CHECK(result.signal == 9);
        CHECK(result.error.empty());
    }
    CHECK(elapsed < std::chrono::seconds(1));
}
