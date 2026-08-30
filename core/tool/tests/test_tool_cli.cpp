#include <aos/tool.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <string>
#include <vector>

extern "C" int aos_tool_cli_main(int, char **);
extern "C" int aos_contact_cli_main(int, char **);

TEST_CASE("tool CLI adds lists replaces and removes registrations") {
    aos::tool::test::TempWorld world("cli-tool");
    const std::string root = world.path.string();
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "add", "echo", "--folder", root, "--", "echo"}) ==
          0);
    const auto echo = aos::tool::read_spec(world.path, "echo");
    REQUIRE(echo.has_value());
    CHECK(echo->name == "echo");
    CHECK(echo->argv == std::vector<std::string>{"echo"});
    CHECK_FALSE(echo->description.empty());

    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "add", "echo", "--folder", root, "--", "echo"}) ==
          1);
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "add", "echo", "--folder", root, "--replace",
               "--description", "新的說明", "--", "echo"}) == 0);
    CHECK(aos::tool::read_spec(world.path, "echo")->description == "新的說明");
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "ls", "--folder", root}) == 0);
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "rm", "echo", "--folder", root}) == 0);
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "rm", "echo", "--folder", root}) == 1);
}

TEST_CASE("tool CLI takes descriptions and fields from metainfo") {
    aos::tool::test::TempWorld world("cli-meta");
    const auto script = world.write_script(
        "fake-metainfo.sh",
        "#!/bin/sh\n"
        "echo '{\"description\":\"CLI 假工具\",\"args\":\"none\"}'\n");
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "add", "fake", "--folder", world.path.string(),
               "--", script.string()}) == 0);
    const auto fake = aos::tool::read_spec(world.path, "fake");
    REQUIRE(fake.has_value());
    CHECK(fake->description == "CLI 假工具");
    CHECK(fake->source == "metainfo");
    CHECK(fake->args == "none");
}

TEST_CASE("tool CLI rejects a missing executable before probing") {
    aos::tool::test::TempWorld world("cli-missing");
    const std::filesystem::path missing = world.path / "does-not-exist";
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "add", "missing", "--folder",
               world.path.string(), "--", missing.string()}) == 1);
    CHECK_FALSE(std::filesystem::exists(
        aos::tool::spec_path(world.path, "missing")));
}

TEST_CASE("tool CLI rejects a missing executable with a description") {
    aos::tool::test::TempWorld world("cli-missing-description");
    const std::filesystem::path missing = world.path / "does-not-exist";
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "add", "missing", "--folder",
               world.path.string(), "--description", "測試", "--",
               missing.string()}) == 1);
    CHECK_FALSE(std::filesystem::exists(
        aos::tool::spec_path(world.path, "missing")));
}

TEST_CASE("tool CLI still registers an existing executable") {
    aos::tool::test::TempWorld world("cli-existing");
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main,
              {"aos tool", "add", "shell", "--folder",
               world.path.string(), "--description", "系統 shell",
               "--no-probe", "--", "/bin/sh"}) == 0);
    const auto shell = aos::tool::read_spec(world.path, "shell");
    REQUIRE(shell.has_value());
    CHECK(shell->argv == std::vector<std::string>{"/bin/sh"});
    CHECK(shell->description == "系統 shell");
}

TEST_CASE("tool CLI help succeeds in any position") {
    CHECK(aos::tool::test::run_cli(
              aos_tool_cli_main, {"aos tool", "add", "name", "--help"}) ==
          0);
    CHECK(aos::tool::test::run_cli(
              aos_contact_cli_main,
              {"aos contact", "add", "name", "folder", "-h"}) == 0);
}

TEST_CASE("contact CLI stores the peer folder verbatim") {
    aos::tool::test::TempWorld world("cli-contact");
    CHECK(aos::tool::test::run_cli(
              aos_contact_cli_main,
              {"aos contact", "add", "bob", "../bob", "--folder-root",
               world.path.string()}) == 0);
    const auto contacts = aos::tool::read_contacts(world.path);
    REQUIRE(contacts.size() == 1);
    CHECK(contacts[0].name == "bob");
    CHECK(contacts[0].folder == "../bob");
}
