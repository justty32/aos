#include "test_support.hpp"

using namespace aos::loop;
using namespace aos::loop::test;

TEST_CASE("deliver publishes one parseable instruction without a tmp file") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    const aos::wire::Inst inst = command("hello", {"echo", "hi"});
    std::string error;

    REQUIRE(deliver(layout, inst, error));
    const std::string path = layout.inbox + "/hello.json";
    REQUIRE(std::filesystem::exists(path));
    CHECK_FALSE(std::filesystem::exists(path + ".tmp"));

    auto parsed = aos::wire::parse_inst(read_file(path), "fallback", error);
    REQUIRE(parsed.has_value());
    CHECK(parsed->id == "hello");
    const std::vector<std::string> expected{"echo", "hi"};
    CHECK(parsed->argv == expected);
}
