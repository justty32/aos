#include "test_run_support.hpp"

using namespace aos::test;

TEST_CASE("exec removes runi after a library-level failure") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_inst(dir, R"({"argv":["/bin/true"],"exit":"."})");

    CHECK(exec_world(dir.path) == 1);
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst.json.runi"));
}

TEST_CASE("exec preserves sequential batch behavior") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_inst(dir,
               R"([{"argv":["/bin/sh","-c","printf first > order"]},{"argv":["/bin/sh","-c","exit 7"]},{"argv":["/bin/sh","-c","test $(cat order) = first && printf second >> order"]}])");

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/order") == "firstsecond");
}

TEST_CASE("exec resolves cwd and stream paths from the world folder") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_file(dir.path + "/input", "hello\n");
    REQUIRE(std::filesystem::create_directory(dir.path + "/sub"));
    write_inst(dir,
               R"([{"argv":["/bin/sh","-c","read x; printf '%s:%s' \"$x\" \"$(pwd)\"; printf error >&2; exit 7"],"stdin":"input","stdout":"output","stderr":"error","exit":"status"},{"argv":["/bin/pwd"],"cwd":"sub","stdout":"subpwd"}])");

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/output") == "hello:" + dir.path);
    CHECK(read_file(dir.path + "/error") == "error");
    CHECK(read_file(dir.path + "/status") == "7\n");
    CHECK(read_file(dir.path + "/subpwd") == dir.path + "/sub\n");
}

TEST_CASE("exec starts the next record while a parallel record is running") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_inst(dir,
               R"([{"argv":["/bin/sh","-c","printf started > started; sleep 1; printf slow > slow"],"parallel":true},{"argv":["/bin/sh","-c","while [ ! -e started ]; do sleep 0.01; done; [ ! -e slow ] && printf fast > fast"]}])");

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/fast") == "fast");
    CHECK(read_file(dir.path + "/slow") == "slow");
}

TEST_CASE("exec joins parallel records before returning") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_inst(dir,
               R"([{"argv":["/bin/sh","-c","sleep 1; [ -e .aos/inst.json.runi ] && printf joined > joined"],"parallel":true}])");

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/joined") == "joined");
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst.json.runi"));
}

TEST_CASE("exec resolves environment directives before running") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    REQUIRE(setenv("AOS_TEST_RESOLVE_VALUE", "resolved-value", 1) == 0);
    write_inst(dir,
               R"({"argv":["/bin/sh","-c","printf %s \"$1\" > result","sh",{"$env":"AOS_TEST_RESOLVE_VALUE"}]})");

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/result") == "resolved-value");
    CHECK(unsetenv("AOS_TEST_RESOLVE_VALUE") == 0);
}
