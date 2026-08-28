#include "test_run_support.hpp"

#include <cstdio>
#include <string>

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
    // 空轉（沒有 inst.json 可跑）不是一個回合，PC 不動（§B-3）。
    CHECK(read_file(dir.path + "/.aos/turn") == "0\n");
    REQUIRE(std::filesystem::remove(dir.path + "/.aos/inst.tempd"));
    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/.aos/turn") == "0\n");
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
    // 彙整發布的批旁邊有 header sidecar（CLI 這條路徑也一樣）。
    CHECK(std::filesystem::exists(dir.path + "/.aos/inst-head.json"));
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
    // release 成功後 PC 遞增（spec 驗收 4，§B-3）。
    CHECK(read_file(dir.path + "/.aos/turn") == "1\n");

    write_inst(dir,
               R"({"argv":["/bin/sh","-c","printf second > second"]})");
    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/second") == "second");
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst.json.runi"));
    CHECK(read_file(dir.path + "/.aos/turn") == "2\n");
}

TEST_CASE("exec treats a missing turn file as zero in an old world") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    // 模擬 M1 之前建立的舊世界：沒有 turn 這個檔（裁-5／§B-3）。
    REQUIRE(std::filesystem::remove(dir.path + "/.aos/turn"));
    write_inst(dir, R"({"argv":["/bin/sh","-c","printf first > first"]})");

    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/first") == "first");
    CHECK(read_file(dir.path + "/.aos/turn") == "1\n");
    // 純新增，不動版面版本。
    CHECK(read_file(dir.path + "/.aos/version") == "1\n");
}

// ── #6：拒絕啟動要擺在彙整之前，不留下不可逆的副作用 ─────────────────────────

TEST_CASE("aos exec 在 .runi 已存在時不彙整", "[run][handoff]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    write_file(inbox + "/z.json",
               R"({"argv":["/bin/sh","-c","printf ran > ran"]})");
    write_file(dir.path + "/.aos/inst.json.runi", "[]");

    const std::string captured = dir.path + "/stderr.txt";
    int status = 0;
    {
        ScopedFd err(STDERR_FILENO, captured, O_WRONLY | O_CREAT | O_TRUNC);
        status = exec_world(dir.path);
    }
    CHECK(status == 3);
    // 三個不可逆動作一個都沒做：投遞還在、沒發布新批、沒寫 header。
    CHECK(read_file(inbox + "/z.json") ==
          R"({"argv":["/bin/sh","-c","printf ran > ran"]})");
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst.json"));
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst-head.json"));
    CHECK_FALSE(std::filesystem::exists(dir.path + "/ran"));
    CHECK(read_file(dir.path + "/.aos/turn") == "0\n");
    CHECK(read_file(captured).find(
              "refusing " + dir.path + ": .aos/inst.json.runi already exists") !=
          std::string::npos);
}

// ── 重導向開檔失敗不再是全靜默 ──────────────────────────────────────────────

TEST_CASE("重導向開檔失敗會在 stderr 留下 warning", "[run][exec]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_file(dir.path + "/.aos/inst.json",
               R"({"argv":["/bin/true"],"stdout":"missing/out"})");

    const std::string captured = dir.path + "/stderr.txt";
    int status = 0;
    {
        ScopedFd err(STDERR_FILENO, captured, O_WRONLY | O_CREAT | O_TRUNC);
        status = exec_world(dir.path);
    }
    // 退出碼不變：重導向開檔失敗是子行程的事（§D-9 的 0）。
    CHECK(status == 0);
    CHECK(read_file(captured).find(
              "aos exec: warning: cannot open redirect target: missing/out") !=
          std::string::npos);
}
