#include "../src/run.hpp"

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

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

void write_inst(const TempDir &dir, const std::string &content) {
    write_file(dir.path + "/.aos/inst.json", content);
}

}  // namespace

TEST_CASE("init creates version 1 and rejects an existing .aos directory") {
    TempDir dir;

    CHECK(init_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/.aos/version") == "1\n");
    CHECK(init_world(dir.path) == 1);
    CHECK(read_file(dir.path + "/.aos/version") == "1\n");
}

TEST_CASE("init rejects a nonexistent folder and both commands validate usage") {
    TempDir parent;
    std::string missing = parent.path + "/missing";
    CHECK(init_world(missing) == 1);

    char init_program[] = "aos init";
    char exec_program[] = "aos exec";
    char *init_argv[] = {init_program};
    char *exec_argv[] = {exec_program};
    CHECK(aos::run_init(1, init_argv) == 2);
    CHECK(aos::run_exec(1, exec_argv) == 2);
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
