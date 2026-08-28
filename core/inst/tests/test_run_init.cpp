#include "test_run_support.hpp"

#include <cstdio>
#include <string>

using namespace aos::test;

namespace {

// CLI 直接寫真的 fd，測試跟它在同一個 process 裡，只能把描述子換成檔案再換回來。
class ScopedFd {
public:
    ScopedFd(int target, const std::string &path, int flags)
        : target_(target), saved_(dup(target)) {
        REQUIRE(saved_ >= 0);
        const int fd = open(path.c_str(), flags, 0666);
        REQUIRE(fd >= 0);
        std::fflush(nullptr);
        REQUIRE(dup2(fd, target_) >= 0);
        close(fd);
    }
    ~ScopedFd() {
        std::fflush(nullptr);
        dup2(saved_, target_);
        close(saved_);
    }

private:
    int target_;
    int saved_;
};

// `aos init` 寫的 `.aos/.gitignore`，一字不差（SPEC §E-4）。
const char *const kGitignore =
    "# aos 版面暫態（SPEC §E-4）：機器暫態不進 git。\n"
    "# version 與 turn 是可攜的回合座標，MUST 納入，所以這裡不排除。\n"
    "# inst.json 與 inst-head.json 是 MAY——要不要讓回滾重演舊回合由你決定。\n"
    "*.temp\n"
    "*.runi\n"
    "*.bad\n"
    "*.tempd/\n";

}  // namespace

TEST_CASE("init creates version 1 and rejects an existing .aos directory") {
    TempDir dir;

    CHECK(init_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/.aos/version") == "1\n");
    CHECK(read_file(dir.path + "/.aos/turn") == "0\n");
    CHECK(std::filesystem::is_directory(dir.path + "/.aos/inst.tempd"));
    CHECK(init_world(dir.path) == 1);
    CHECK(read_file(dir.path + "/.aos/version") == "1\n");
    CHECK(read_file(dir.path + "/.aos/turn") == "0\n");
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
        CHECK(read_file(".aos/turn") == "0\n");
        write_file(".aos/inst.json",
                   R"({"argv":["/bin/sh","-c","printf current > current"]})");
        CHECK(aos::run_exec(1, exec_argv) == 0);
        CHECK(read_file("current") == "current");
    }
    CHECK(std::filesystem::current_path() == original);
}

// ── #14：`aos init` 是 §E-4 gitignore 政策的執行者 ────────────────────────────

TEST_CASE("init 建立 .aos/.gitignore（§E-4）", "[run][init]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/.aos/.gitignore") == std::string(kGitignore));

    // 已存在的世界仍然拒絕，`.gitignore` 也不被動到（既有行為不變）。
    CHECK(init_world(dir.path) == 1);
    CHECK(read_file(dir.path + "/.aos/.gitignore") == std::string(kGitignore));
}

TEST_CASE("exec 與 deliver 都不要求舊世界有 .gitignore", "[run][init]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    REQUIRE(std::filesystem::remove(dir.path + "/.aos/.gitignore"));
    CHECK(exec_world(dir.path) == 0);
}

// ── `.aos` 是普通檔 vs. 是目錄：兩種 EEXIST 要印得出差別 ──────────────────────

TEST_CASE("init 對 .aos 是普通檔印 Not a directory", "[run][init]") {
    TempDir dir;
    write_file(dir.path + "/.aos", "not a directory\n");
    const std::string captured = dir.path + "/stderr.txt";
    int status = 0;
    {
        ScopedFd err(STDERR_FILENO, captured, O_WRONLY | O_CREAT | O_TRUNC);
        status = init_world(dir.path);
    }
    CHECK(status == 1);
    const std::string message = read_file(captured);
    CHECK(message.find("aos init: invalid ") != std::string::npos);
    CHECK(message.find("/.aos: Not a directory") != std::string::npos);
}

TEST_CASE("init 對已存在的 .aos 目錄維持 already exists", "[run][init]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string captured = dir.path + "/stderr.txt";
    int status = 0;
    {
        ScopedFd err(STDERR_FILENO, captured, O_WRONLY | O_CREAT | O_TRUNC);
        status = init_world(dir.path);
    }
    CHECK(status == 1);
    CHECK(read_file(captured).find(".aos already exists") != std::string::npos);
}
