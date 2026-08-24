#include "test_run_support.hpp"

using namespace aos::test;

TEST_CASE("init creates version 1 and rejects an existing .aos directory") {
    TempDir dir;

    CHECK(init_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/.aos/version") == "1\n");
    CHECK(std::filesystem::is_directory(dir.path + "/.aos/inst.tempd"));
    CHECK(init_world(dir.path) == 1);
    CHECK(read_file(dir.path + "/.aos/version") == "1\n");
}

TEST_CASE("init rejects a nonexistent folder and commands reject extra arguments") {
    TempDir parent;
    std::string missing = parent.path + "/missing";
    CHECK(init_world(missing) == 1);

    char init_program[] = "aos init";
    char exec_program[] = "aos exec";
    char extra[] = "extra";
    char more[] = "more";
    char *init_argv[] = {init_program, extra, more};
    char *exec_argv[] = {exec_program, extra, more};
    CHECK(aos::run_init(3, init_argv) == 2);
    CHECK(aos::run_exec(3, exec_argv) == 2);
}

TEST_CASE("init and exec default their folder to the current directory") {
    TempDir dir;
    const std::filesystem::path original = std::filesystem::current_path();
    {
        ScopedCwd cwd(dir.path);
        char init_program[] = "aos init";
        char exec_program[] = "aos exec";
        char *init_argv[] = {init_program};
        char *exec_argv[] = {exec_program};
        REQUIRE(aos::run_init(1, init_argv) == 0);
        CHECK(read_file(".aos/version") == "1\n");
        write_file(".aos/inst.json",
                   R"({"argv":["/bin/sh","-c","printf current > current"]})");
        CHECK(aos::run_exec(1, exec_argv) == 0);
        CHECK(read_file("current") == "current");
    }
    CHECK(std::filesystem::current_path() == original);
}
