#include <aos/tool.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <fstream>

namespace {

aos::tool::Spec make_spec(std::string name, std::string description) {
    aos::tool::Spec spec;
    spec.name = std::move(name);
    spec.argv = {spec.name};
    spec.description = std::move(description);
    return spec;
}

}  // namespace

TEST_CASE("tool registry writes reads sorts and removes specs") {
    aos::tool::test::TempWorld world("registry");
    CHECK(aos::tool::read_registry(world.path).empty());

    aos::tool::write_spec(world.path, make_spec("zeta", "最後"));
    aos::tool::write_spec(world.path, make_spec("alpha", "最先"));
    const auto alpha = aos::tool::read_spec(world.path, "alpha");
    REQUIRE(alpha.has_value());
    CHECK(alpha->description == "最先");

    const auto registry = aos::tool::read_registry(world.path);
    REQUIRE(registry.size() == 2);
    CHECK(registry[0].name == "alpha");
    CHECK(registry[1].name == "zeta");
    CHECK(aos::tool::remove_spec(world.path, "alpha"));
    CHECK_FALSE(aos::tool::remove_spec(world.path, "alpha"));

    std::ifstream input(aos::tool::spec_path(world.path, "zeta"));
    nlohmann::json written;
    CHECK_NOTHROW(input >> written);
    CHECK(written["name"] == "zeta");
}

TEST_CASE("tool default installation only fills an empty registry") {
    aos::tool::test::TempWorld world("defaults");
    CHECK(aos::tool::install_defaults(world.path));
    REQUIRE(aos::tool::read_registry(world.path).size() == 3);

    aos::tool::Spec changed = *aos::tool::read_spec(world.path, "ls");
    changed.description = "使用者自己的說明";
    aos::tool::write_spec(world.path, changed);
    CHECK_FALSE(aos::tool::install_defaults(world.path));
    CHECK(aos::tool::read_spec(world.path, "ls")->description ==
          "使用者自己的說明");
}

TEST_CASE("say tool installation writes once without replacing local edits") {
    aos::tool::test::TempWorld world("say-default");
    CHECK(aos::tool::install_say_tool(world.path));

    const auto installed = aos::tool::read_spec(world.path, "say");
    REQUIRE(installed.has_value());
    CHECK(installed->argv == std::vector<std::string>{"aos", "say", "--to"});
    CHECK(installed->args == "list");
    CHECK(installed->timeout_ms == 10000);
    CHECK(installed->guarantee == "at-least-once");
    CHECK(installed->predictability == "high");

    aos::tool::Spec changed = *installed;
    changed.description = "使用者自己的 say 說明";
    aos::tool::write_spec(world.path, changed);
    CHECK_FALSE(aos::tool::install_say_tool(world.path));
    CHECK(aos::tool::read_spec(world.path, "say")->description ==
          "使用者自己的 say 說明");
}

TEST_CASE("tool registry rejects a name that differs from its filename") {
    aos::tool::test::TempWorld world("filename");
    aos::tool::write_spec(world.path, make_spec("actual", "說明"));
    std::filesystem::rename(aos::tool::spec_path(world.path, "actual"),
                            aos::tool::tools_dir(world.path) / "other.json");
    CHECK_THROWS(aos::tool::read_registry(world.path));
}
