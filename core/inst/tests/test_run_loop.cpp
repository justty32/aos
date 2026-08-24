#include "test_run_support.hpp"

#include <algorithm>
#include <signal.h>
#include <sys/wait.h>

using namespace aos::test;

TEST_CASE("exec loop validates its interval arguments") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);

    char program[] = "aos exec";
    char option[] = "--loop";
    char text[] = "later";
    char negative[] = "-1";
    char zero[] = "0";
    char extra[] = "extra";
    char *missing[] = {program, option};
    char *nonnumeric[] = {program, option, text};
    char *below_zero[] = {program, option, negative};
    char *too_many[] = {program, option, zero, dir.path.data(), extra};
    CHECK(aos::run_exec(2, missing) == 2);
    CHECK(aos::run_exec(3, nonnumeric) == 2);
    CHECK(aos::run_exec(3, below_zero) == 2);
    CHECK(aos::run_exec(5, too_many) == 2);

    write_file(dir.path + "/.aos/inst.json.runi", "busy\n");
    CHECK(loop_world(dir.path, zero) == 3);
}

TEST_CASE("exec loop defaults its folder to the current directory") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_file(dir.path + "/.aos/inst.json.runi", "busy\n");
    const std::filesystem::path original = std::filesystem::current_path();
    {
        ScopedCwd cwd(dir.path);
        char program[] = "aos exec";
        char option[] = "--loop";
        char interval[] = "250";
        char *argv[] = {program, option, interval};
        CHECK(aos::run_exec(3, argv) == 3);
    }
    CHECK(std::filesystem::current_path() == original);
}

TEST_CASE("exec loop advances consecutive rounds and stops cleanly on signal") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_inst(
        dir,
        R"({"argv":["/bin/sh","-c","printf '%s' '{\"argv\":[\"/bin/sh\",\"-c\",\"printf second > second\"]}' > .aos/inst.tempd/next.json; printf first > first"],"exit":"."})");

    const pid_t child = fork();
    REQUIRE(child >= 0);
    if (child == 0) {
        char interval[] = "1000";
        _exit(loop_world(dir.path, interval));
    }

    REQUIRE(wait_for_file(dir.path + "/second"));
    REQUIRE(kill(child, SIGTERM) == 0);
    int status = 0;
    REQUIRE(waitpid(child, &status, 0) == child);
    REQUIRE(WIFEXITED(status));
    CHECK(WEXITSTATUS(status) == 0);
    CHECK(read_file(dir.path + "/first") == "first");
    CHECK(read_file(dir.path + "/second") == "second");
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst.json.runi"));
}

TEST_CASE("exec loop throttles failures that happen before a round starts") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_file(dir.path + "/.aos/version", "99\n");
    const std::string errors = dir.path + "/errors";

    const pid_t child = fork();
    REQUIRE(child >= 0);
    if (child == 0) {
        std::freopen(errors.c_str(), "w", stderr);
        char interval[] = "200";
        const int result = loop_world(dir.path, interval);
        std::fflush(stderr);
        _exit(result);
    }
    usleep(550000);
    REQUIRE(kill(child, SIGTERM) == 0);
    int status = 0;
    REQUIRE(waitpid(child, &status, 0) == child);
    REQUIRE(WIFEXITED(status));
    CHECK(WEXITSTATUS(status) == 0);

    const std::string output = read_file(errors);
    const std::size_t lines =
        static_cast<std::size_t>(std::count(output.begin(), output.end(), '\n'));
    CHECK(lines >= 1);
    CHECK(lines <= 5);
}

TEST_CASE("exec loop does not run another round after a signal wakes idle sleep") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);

    const pid_t child = fork();
    REQUIRE(child >= 0);
    if (child == 0) {
        char interval[] = "1000";
        _exit(loop_world(dir.path, interval));
    }
    usleep(200000);
    const std::string delivery = dir.path + "/.aos/inst.tempd/next.json";
    write_file(delivery,
               R"({"argv":["/bin/sh","-c","printf ran > unexpected"]})");
    REQUIRE(kill(child, SIGTERM) == 0);
    int status = 0;
    REQUIRE(waitpid(child, &status, 0) == child);
    REQUIRE(WIFEXITED(status));
    CHECK(WEXITSTATUS(status) == 0);
    CHECK(std::filesystem::exists(delivery));
    CHECK_FALSE(std::filesystem::exists(dir.path + "/unexpected"));
}
