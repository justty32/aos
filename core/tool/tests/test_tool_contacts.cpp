#include <aos/tool.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <fstream>
#include <optional>

namespace {

class ScopedHome {
public:
    explicit ScopedHome(const std::filesystem::path &path) {
        if (const char *value = std::getenv("HOME")) original_ = value;
        REQUIRE(setenv("HOME", path.c_str(), 1) == 0);
    }
    ~ScopedHome() {
        if (original_) setenv("HOME", original_->c_str(), 1);
        else unsetenv("HOME");
    }

private:
    std::optional<std::string> original_;
};

}  // namespace

TEST_CASE("contacts add replace find and remove entries") {
    aos::tool::test::TempWorld world("contacts");
    const std::filesystem::path home = world.path / "home";
    std::filesystem::create_directories(home);
    ScopedHome scoped_home(home);
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

TEST_CASE("user contact is synthetic and an explicit entry overrides it") {
    aos::tool::test::TempWorld world("user-contact");
    const std::filesystem::path home = world.path / "home";
    std::filesystem::create_directories(home);
    ScopedHome scoped_home(home);

    const aos::tool::Contact user = aos::tool::user_contact();
    CHECK(user.name == "~");
    CHECK(user.folder ==
          std::filesystem::absolute(home).lexically_normal().string());
    CHECK(aos::tool::read_contacts(world.path).empty());

    const auto found = aos::tool::find_contact(world.path, "~");
    REQUIRE(found.has_value());
    CHECK(found->folder == user.folder);
    CHECK(aos::tool::read_contacts(world.path).empty());

    aos::tool::add_contact(world.path, {"bob", "../bob", "", ""});
    std::ifstream input(aos::tool::contacts_path(world.path));
    const std::string stored{std::istreambuf_iterator<char>(input),
                             std::istreambuf_iterator<char>()};
    CHECK(stored.find("\"~\"") == std::string::npos);

    aos::tool::add_contact(world.path,
                           {"~", "/explicit-user", "owner", "覆寫"});
    const auto overridden = aos::tool::find_contact(world.path, "~");
    REQUIRE(overridden.has_value());
    CHECK(overridden->folder == "/explicit-user");
    CHECK(overridden->agent == "owner");
}
