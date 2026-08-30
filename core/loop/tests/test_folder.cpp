#include "test_support.hpp"

using namespace aos::loop;
using namespace aos::loop::test;

TEST_CASE("find_folder finds the nearest parent world") {
    TempDir dir;
    const std::filesystem::path world =
        std::filesystem::path(dir.path) / "W";
    const std::filesystem::path deep = world / "sub" / "deep";
    REQUIRE(std::filesystem::create_directories(world / ".aos"));
    REQUIRE(std::filesystem::create_directories(deep));

    const std::string found = find_folder(deep.string());
    REQUIRE_FALSE(found.empty());
    CHECK(std::filesystem::equivalent(found, world));
}

TEST_CASE("find_folder returns empty outside a world") {
    TempDir dir;
    CHECK(find_folder(dir.path).empty());
}
