#include <aos/tool.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <fstream>

TEST_CASE("contacts add replace find and remove entries") {
    aos::tool::test::TempWorld world("contacts");
    CHECK(aos::tool::read_contacts(world.path).empty());
    CHECK_FALSE(aos::tool::find_contact(world.path, "bob").has_value());

    aos::tool::add_contact(world.path,
                           {"bob", "../bob-world", "", "部署"});
    auto bob = aos::tool::find_contact(world.path, "bob");
    REQUIRE(bob.has_value());
    CHECK(bob->folder == "../bob-world");
    CHECK(bob->note == "部署");

    aos::tool::add_contact(world.path,
                           {"bob", "../new-bob", "reviewer", ""});
    REQUIRE(aos::tool::read_contacts(world.path).size() == 1);
    bob = aos::tool::find_contact(world.path, "bob");
    REQUIRE(bob.has_value());
    CHECK(bob->folder == "../new-bob");
    CHECK(bob->agent == "reviewer");

    std::ifstream input(aos::tool::contacts_path(world.path));
    nlohmann::json written;
    input >> written;
    CHECK(written.is_array());

    CHECK(aos::tool::remove_contact(world.path, "bob"));
    CHECK_FALSE(aos::tool::remove_contact(world.path, "bob"));
    CHECK(aos::tool::read_contacts(world.path).empty());
}
