#include "test_run_support.hpp"

#include <cstdio>
#include <string>

#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/wait.h>

using namespace aos::test;

namespace {

// CLI 直接寫真的 fd，而測試跟它在同一個 process 裡，所以只能把描述子換成檔案再換
// 回來（與 test_run_deliver.cpp 同款；test_run_support.hpp 是別人的檔，不動它）。
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

// 空批次：claim → execute → release 全走完，但一個子行程都不生、一個位元組都不寫，
// 於是整趟 exec 裡唯一會寫檔的地方就只剩 advance_turn。
void put_empty_batch(const TempDir &dir) {
    write_file(dir.path + "/.aos/inst.json", "[]");
}

int deliver_file(const std::string &folder, const std::string &file,
                 const std::string &sink) {
    std::string program = "aos deliver";
    std::string world = folder;
    std::string option = "-f";
    std::string input = file;
    char *argv[] = {program.data(), world.data(), option.data(), input.data()};
    ScopedFd out(STDOUT_FILENO, sink, O_WRONLY | O_CREAT | O_TRUNC);
    return aos::run_deliver(4, argv);
}

}  // namespace

// ── #19：版面版本比對放寬到 §B-4 立法的範圍 ──────────────────────────────────

TEST_CASE("exec 接受尾端空白不同的版面版本 1", "[run][version]") {
    for (const char *content : {"1", "1\n", "1\n\n", "1 \n", "1\r\n", "1\t"}) {
        TempDir dir;
        REQUIRE(init_world(dir.path) == 0);
        write_file(dir.path + "/.aos/version", content);
        INFO("version = " << std::string(content));
        CHECK(exec_world(dir.path) == 0);
    }
}

TEST_CASE("exec 拒絕不是 1 的版面版本", "[run][version]") {
    for (const char *content : {"0\n", "2\n", "", "abc\n", "11\n", " 1\n"}) {
        TempDir dir;
        REQUIRE(init_world(dir.path) == 0);
        write_file(dir.path + "/.aos/version", content);
        INFO("version = " << std::string(content));
        CHECK(exec_world(dir.path) == 1);
    }
}

TEST_CASE("deliver 的版面版本比對與 exec 同一套", "[run][version][deliver]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string input = dir.path + "/payload.json";
    const std::string sink = dir.path + "/stdout.txt";
    write_file(input, R"({"argv":["/bin/true"]})");

    write_file(dir.path + "/.aos/version", "1");
    CHECK(deliver_file(dir.path, input, sink) == 0);

    write_file(dir.path + "/.aos/version", "2\n");
    CHECK(deliver_file(dir.path, input, sink) == 1);
}

// ── #27：turn 溢位大聲拒絕，不靜默回繞 ──────────────────────────────────────

TEST_CASE("exec 在 turn 已達 UINT64_MAX 時拒絕遞增", "[run][turn]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    write_file(dir.path + "/.aos/turn", "18446744073709551615\n");
    put_empty_batch(dir);

    const std::string captured = dir.path + "/stderr.txt";
    int status = 0;
    {
        ScopedFd err(STDERR_FILENO, captured, O_WRONLY | O_CREAT | O_TRUNC);
        status = exec_world(dir.path);
    }
    CHECK(status == 1);
    // PC 不動、不回繞成 0。
    CHECK(read_file(dir.path + "/.aos/turn") == "18446744073709551615\n");
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/turn.temp"));
    CHECK(read_file(captured).find("cannot advance") != std::string::npos);
}

// ── #22(a)：advance_turn 失敗不留 turn.temp 殘骸 ────────────────────────────

TEST_CASE("turn.temp 被目錄佔住時 exec 回 1 且不動 turn", "[run][turn]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    // 佔成目錄：advance_turn 的 open(O_WRONLY|O_CREAT) 會回 EISDIR。
    REQUIRE(std::filesystem::create_directory(dir.path + "/.aos/turn.temp"));
    put_empty_batch(dir);

    const std::string captured = dir.path + "/stderr.txt";
    int status = 0;
    {
        ScopedFd err(STDERR_FILENO, captured, O_WRONLY | O_CREAT | O_TRUNC);
        status = exec_world(dir.path);
    }
    CHECK(status == 1);
    CHECK(read_file(dir.path + "/.aos/turn") == "0\n");
    // 本函式沒建出任何檔案殘骸；預先佔位的那個目錄不是它的，不會被誤刪。
    CHECK(std::filesystem::is_directory(dir.path + "/.aos/turn.temp"));
    CHECK(read_file(captured).find("cannot advance") != std::string::npos);
}

// ── #22(b)：SIGXFSZ 在 advance_turn 範圍內被忽略，write 誠實回 EFBIG ────────

TEST_CASE("RLIMIT_FSIZE 觸頂時 exec 回 1 而不是被 SIGXFSZ 砍死", "[run][turn]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    put_empty_batch(dir);
    std::string world = dir.path;

    // RLIMIT_FSIZE 是行程層級的，套在測試行程自己身上會連 Catch2 的輸出一起搞死，
    // 所以 fork 一個只跑這一趟的子行程。子行程的 stdout／stderr 先導到 /dev/null
    // （字元裝置不受 RLIMIT_FSIZE 管），空批次讓 advance_turn 成為唯一的寫檔點。
    std::fflush(nullptr);
    const pid_t pid = fork();
    REQUIRE(pid >= 0);
    if (pid == 0) {
        const int null_fd = open("/dev/null", O_WRONLY);
        if (null_fd >= 0) {
            dup2(null_fd, STDOUT_FILENO);
            dup2(null_fd, STDERR_FILENO);
            if (null_fd > STDERR_FILENO) close(null_fd);
        }
        struct rlimit limit {};
        limit.rlim_cur = 0;
        limit.rlim_max = 0;
        if (setrlimit(RLIMIT_FSIZE, &limit) != 0) _exit(90);
        _exit(exec_world(world) == 1 ? 0 : 91);
    }
    int raw_status = 0;
    REQUIRE(waitpid(pid, &raw_status, 0) == pid);
    // 沒被訊號砍死（SIGXFSZ 已在 advance_turn 範圍內忽略），而且真的走了錯誤路徑。
    CHECK(WIFEXITED(raw_status));
    CHECK(WEXITSTATUS(raw_status) == 0);
    CHECK(read_file(dir.path + "/.aos/turn") == "0\n");
    // 走過錯誤路徑的 turn.temp 被自己清掉了，不留給 M3 的 aos recover。
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/turn.temp"));
}
