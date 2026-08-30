#include <aos/exec.hpp>

#include <catch2/catch_test_macros.hpp>

#include <vector>

TEST_CASE("wait_all 在每條子行程收線時分別記錄 ended_at") {
    const std::vector<aos::exec::Spawn> spawns{
        {.argv = {"true"}},
        {.argv = {"sh", "-c", "sleep 0.3"}},
    };

    auto running = aos::exec::start_all(spawns);
    const auto results = aos::exec::wait_all(running);

    REQUIRE(results.size() == 2);
    REQUIRE(results[0].exit == 0);
    REQUIRE(results[1].exit == 0);
    CHECK_FALSE(results[0].ended_at.empty());
    CHECK_FALSE(results[1].ended_at.empty());
    CHECK(results[0].ended_at != results[1].ended_at);
}
