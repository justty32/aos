#include "../src/run.hpp"

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <signal.h>
#include <sstream>
#include <string>
#include <sys/wait.h>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace {

std::string read_file(const std::string &path) {
    std::ifstream input(path);
    std::ostringstream content;
    content << input.rdbuf();
    return content.str();
}

void write_file(const std::string &path, const std::string &content) {
    std::ofstream output(path, std::ios::out | std::ios::trunc);
    output << content;
}

std::string make_temp_dir() {
    std::string pattern = "/tmp/aos_run_test_XXXXXX";
    std::vector<char> buffer(pattern.begin(), pattern.end());
    buffer.push_back('\0');
    REQUIRE(mkdtemp(buffer.data()) != nullptr);
    return buffer.data();
}

struct TempDir {
    TempDir() : path(make_temp_dir()) {}
    ~TempDir() { std::filesystem::remove_all(path); }
    std::string path;
};

class ScopedCwd {
public:
    explicit ScopedCwd(const std::string &path)
        : saved_(open(".", O_RDONLY | O_DIRECTORY | O_CLOEXEC)) {
        REQUIRE(saved_ >= 0);
        REQUIRE(chdir(path.c_str()) == 0);
    }
    ~ScopedCwd() {
        if (saved_ >= 0) {
            fchdir(saved_);
            close(saved_);
        }
    }

private:
    int saved_;
};

int init_world(std::string &path) {
    char program[] = "aos init";
    char *argv[] = {program, path.data()};
    return aos::run_init(2, argv);
}

int exec_world(std::string &path) {
    char program[] = "aos exec";
    char *argv[] = {program, path.data()};
    return aos::run_exec(2, argv);
}

int loop_world(std::string &path, char *interval) {
    char program[] = "aos exec";
    char option[] = "--loop";
    char *argv[] = {program, option, interval, path.data()};
    return aos::run_exec(4, argv);
}

bool wait_for_file(const std::string &path) {
    for (int attempt = 0; attempt < 300; ++attempt) {
        if (std::filesystem::exists(path)) return true;
        usleep(10000);
    }
    return false;
}

void write_inst(const TempDir &dir, const std::string &content) {
    write_file(dir.path + "/.aos/inst.json", content);
}

}  // namespace

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

TEST_CASE("exec requires .aos and a recognized version") {
    TempDir missing_aos;
    CHECK(exec_world(missing_aos.path) == 1);

    TempDir missing_version;
    REQUIRE(std::filesystem::create_directory(missing_version.path + "/.aos"));
    CHECK(exec_world(missing_version.path) == 1);

    TempDir unknown_version;
    REQUIRE(std::filesystem::create_directory(unknown_version.path + "/.aos"));
    write_file(unknown_version.path + "/.aos/version", "2\n");
    CHECK(exec_world(unknown_version.path) == 1);
}

TEST_CASE("exec returns zero when no instruction is waiting") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    CHECK(exec_world(dir.path) == 0);
    REQUIRE(std::filesystem::remove(dir.path + "/.aos/inst.tempd"));
    CHECK(exec_world(dir.path) == 0);
}

TEST_CASE("exec aggregates two deliveries and removes them after publishing") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    write_file(inbox + "/20.json",
               R"({"argv":["/bin/sh","-c","printf second > second"]})");
    write_file(inbox + "/10.json",
               R"({"argv":["/bin/sh","-c","printf first > first"]})");

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/first") == "first");
    CHECK(read_file(dir.path + "/second") == "second");
    CHECK_FALSE(std::filesystem::exists(inbox + "/10.json"));
    CHECK_FALSE(std::filesystem::exists(inbox + "/20.json"));
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst.json.runi"));
}

TEST_CASE("exec isolates invalid deliveries and ignores status suffixes") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    write_file(inbox + "/bad.json", "not json");
    write_file(inbox + "/good.json",
               R"({"argv":["/bin/sh","-c","printf good > good"]})");
    write_file(inbox + "/later.json.temp",
               R"({"argv":["/bin/sh","-c","printf temp > temp"]})");
    write_file(inbox + "/old.json.bad",
               R"({"argv":["/bin/sh","-c","printf bad > bad"]})");

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/good") == "good");
    CHECK(std::filesystem::exists(inbox + "/bad.json.bad"));
    CHECK(std::filesystem::exists(inbox + "/later.json.temp"));
    CHECK(std::filesystem::exists(inbox + "/old.json.bad"));
    CHECK_FALSE(std::filesystem::exists(dir.path + "/temp"));
    CHECK_FALSE(std::filesystem::exists(dir.path + "/bad"));
}

TEST_CASE("exec leaves deliveries pending while inst.json already exists") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    write_inst(dir,
               R"({"argv":["/bin/sh","-c","printf current > current"]})");
    write_file(inbox + "/next.json",
               R"({"argv":["/bin/sh","-c","printf next > next"]})");

    REQUIRE(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/current") == "current");
    CHECK(std::filesystem::exists(inbox + "/next.json"));
    CHECK_FALSE(std::filesystem::exists(dir.path + "/next"));

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/next") == "next");
    CHECK_FALSE(std::filesystem::exists(inbox + "/next.json"));
}

TEST_CASE("exec refuses an existing runi with status three") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_file(dir.path + "/.aos/inst.json.runi", "crash\n");
    CHECK(exec_world(dir.path) == 3);
}

TEST_CASE("exec claims the complete input before validating or executing it") {
    TempDir invalid;
    REQUIRE(init_world(invalid.path) == 0);
    const std::string marker = invalid.path + "/marker";
    write_inst(invalid,
               "[{\"argv\":[\"/bin/sh\",\"-c\",\"printf ran > " + marker +
                   "\"]},{\"argv\":[]}]");

    CHECK(exec_world(invalid.path) == 1);
    CHECK_FALSE(std::filesystem::exists(marker));
    CHECK_FALSE(std::filesystem::exists(invalid.path + "/.aos/inst.json"));
    CHECK_FALSE(std::filesystem::exists(invalid.path + "/.aos/inst.json.runi"));

    TempDir valid;
    REQUIRE(init_world(valid.path) == 0);
    write_inst(valid,
               R"({"argv":["/bin/sh","-c","[ ! -e .aos/inst.json ] && [ -e .aos/inst.json.runi ] && printf claimed > claimed"]})");
    CHECK(exec_world(valid.path) == 0);
    CHECK(read_file(valid.path + "/claimed") == "claimed");
    CHECK_FALSE(std::filesystem::exists(valid.path + "/.aos/inst.json.runi"));
}

TEST_CASE("exec can consume two consecutive rounds") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_inst(dir, R"({"argv":["/bin/sh","-c","printf first > first"]})");

    REQUIRE(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/first") == "first");
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst.json.runi"));

    write_inst(dir,
               R"({"argv":["/bin/sh","-c","printf second > second"]})");
    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/second") == "second");
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst.json.runi"));
}

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
