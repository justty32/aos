#include <aos/tool.hpp>

#include "../src/internal.hpp"
#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <optional>
#include <string_view>

namespace {

class ScopedHome {
  public:
    explicit ScopedHome(const std::filesystem::path &path) {
        if (const char *value = std::getenv("HOME")) original_ = value;
        REQUIRE(setenv("HOME", path.c_str(), 1) == 0);
    }
    ~ScopedHome() {
        if (original_)
            setenv("HOME", original_->c_str(), 1);
        else
            unsetenv("HOME");
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

    aos::tool::add_contact(world.path, {"bob", "../bob-world", "", "部署"});
    auto bob = aos::tool::find_contact(world.path, "bob");
    REQUIRE(bob.has_value());
    CHECK(bob->folder == "../bob-world");
    CHECK(bob->note == "部署");

    aos::tool::add_contact(world.path, {"bob", "../new-bob", "reviewer", ""});
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

TEST_CASE("contact status collects live unread counts and isolates bad cells") {
    aos::tool::test::TempWorld workspace("contact-status");
    const std::filesystem::path boss = workspace.path / "boss";
    const std::filesystem::path w1 = workspace.path / "w1";
    const std::filesystem::path home = workspace.path / "home";
    std::filesystem::create_directories(home / ".aos" / "say");
    ScopedHome scoped_home(home);

    const auto write_status = [](const std::filesystem::path &world,
                                 std::string_view agent,
                                 const nlohmann::json &status) {
        const std::filesystem::path path =
            world / ".aos" / "agents" / agent / "status.json";
        std::filesystem::create_directories(path.parent_path() / "say");
        std::ofstream output(path);
        output << status.dump(2) << '\n';
    };
    write_status(boss, "boss",
                 {{"status", "idle"}, {"turn", 12}, {"unread", 99}});
    write_status(
        w1, "w1",
        {{"status", "idle"},
         {"turn", 9},
         {"unread", 0},
         {"last_error", "這是一段超過四十個字而且中間\n帶換行的錯誤訊息"
                        "，用來驗證單行截斷不會弄壞中文字元，後面再補"
                        "上足夠多的內容確保一定超過限制"}});
    const std::filesystem::path w1_say = w1 / ".aos" / "agents" / "w1" / "say";
    for (int index = 0; index < 3; ++index) {
        std::ofstream(w1_say / (std::to_string(index) + ".md")) << "訊息";
    }
    aos::tool::write_contacts(
        boss, {{"w1", "../w1", "", "實機測試"}, {"w2", "../w2", "", "不存在"}});

    std::vector<aos::tool::detail::ContactStatusRow> rows;
    CHECK_NOTHROW(rows = aos::tool::detail::contact_status_rows(boss));
    REQUIRE(rows.size() == 4);
    const auto find = [&](std::string_view name)
        -> const aos::tool::detail::ContactStatusRow & {
        const auto row =
            std::find_if(rows.begin(), rows.end(),
                         [&](const auto &item) { return item.name == name; });
        REQUIRE(row != rows.end());
        return *row;
    };

    const auto &self = find(".");
    REQUIRE(self.unread.has_value());
    CHECK(*self.unread == 0);
    const auto &peer = find("w1");
    CHECK(peer.agent == "w1");
    CHECK(peer.status == "pending");
    REQUIRE(peer.turn.has_value());
    CHECK(*peer.turn == 9);
    REQUIRE(peer.unread.has_value());
    CHECK(*peer.unread == 3);
    CHECK(peer.last_error.find('\n') == std::string::npos);
    CHECK(peer.last_error.ends_with("…"));
    const auto &missing = find("w2");
    CHECK(missing.status == "（找不到 .aos）");
    CHECK_FALSE(missing.unread.has_value());
}
