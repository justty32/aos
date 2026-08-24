#include "test_run_support.hpp"

using namespace aos::test;

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

TEST_CASE("exec resolves an environment directive delivered through handoff") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    write_file(inbox + "/env.json",
               R"({"argv":["/bin/sh","-c","printf '%s' \"$1\" > resolved","sh",{"$env":"AOS_HANDOFF_VALUE"}]})");
    REQUIRE(setenv("AOS_HANDOFF_VALUE", "through-handoff", 1) == 0);

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/resolved") == "through-handoff");
    REQUIRE(unsetenv("AOS_HANDOFF_VALUE") == 0);
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
