#include "../src/run.hpp"

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <string>

namespace {

int run_cli(const char *operation, std::string &path) {
    char program[] = "aos tooljson";
    char *argv[] = {program, const_cast<char *>(operation), path.data()};
    return aos::tooljson::cli_run(3, argv);
}

}  // namespace

TEST_CASE("tooljson check validates without executing") {
    TooljsonTempDir dir;
    std::string path = dir.path + "/valid.json";
    write_tooljson_file(path, exec_spec("safe", {}, "[]",
                                        R"("exec":["definitely-not-run"],"argv":{})"));
    CHECK(run_cli("check", path) == 0);
}

TEST_CASE("tooljson list accepts a multi-tool file") {
    TooljsonTempDir dir;
    std::string path = dir.path + "/tools.json";
    write_tooljson_file(path,
                        "[" + exec_spec("first") + "," +
                            exec_spec("second") + "]");
    CHECK(run_cli("list", path) == 0);
}

TEST_CASE("tooljson check returns nonzero for an invalid spec") {
    TooljsonTempDir dir;
    std::string path = dir.path + "/bad.json";
    write_tooljson_file(path, R"({"type":"function"})");
    CHECK(run_cli("check", path) == 1);
}

TEST_CASE("tooljson CLI rejects run during S1") {
    TooljsonTempDir dir;
    std::string path = dir.path + "/valid.json";
    write_tooljson_file(path, exec_spec());
    CHECK(run_cli("run", path) == 2);
}
