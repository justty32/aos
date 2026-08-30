#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdlib>
#include <filesystem>
#include <initializer_list>
#include <string>
#include <vector>

#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>

extern "C" int aos_run_cli_main(int argc, char *argv[]);
extern "C" int aos_deliver_cli_main(int argc, char *argv[]);

namespace {

class ScopedAosFolder {
  public:
    explicit ScopedAosFolder(const std::string &folder) {
        const char *old = std::getenv("AOS_FOLDER");
        if (old != nullptr) {
            had_old_ = true;
            old_ = old;
        }
        REQUIRE(::setenv("AOS_FOLDER", folder.c_str(), 1) == 0);
    }

    ~ScopedAosFolder() {
        if (had_old_) {
            ::setenv("AOS_FOLDER", old_.c_str(), 1);
        } else {
            ::unsetenv("AOS_FOLDER");
        }
    }

  private:
    bool had_old_ = false;
    std::string old_;
};

int call_cli(int (*entry)(int, char **),
             std::initializer_list<std::string> arguments) {
    std::vector<std::string> storage(arguments);
    std::vector<char *> argv;
    argv.reserve(storage.size());
    for (auto &argument : storage) argv.push_back(argument.data());
    return entry(static_cast<int>(argv.size()), argv.data());
}

void write_every(const aos::loop::Layout &layout, const std::string &name,
                 const std::string &argv_json) {
    aos::loop::test::write_file(
        layout.every + "/" + name + ".json",
        "{\"argv\":" + argv_json + "}\n");
}

}  // namespace

using namespace aos::loop;
using namespace aos::loop::test;

TEST_CASE("aos run 拒絕不存在的明確資料夾且不建立世界") {
    TempDir dir;
    ScopedAosFolder environment(dir.path);
    const std::string missing = dir.path + "/打錯的資料夾";

    const int result = call_cli(
        aos_run_cli_main, {"aos run", missing, "--step", "1"});

    CHECK(result == 1);
    CHECK_FALSE(std::filesystem::exists(missing));
    CHECK_FALSE(std::filesystem::exists(missing + "/.aos"));
}

TEST_CASE("aos run 拒絕不是資料夾的明確路徑") {
    TempDir dir;
    ScopedAosFolder environment(dir.path);
    const std::string file = dir.path + "/world.txt";
    write_file(file, "不是資料夾\n");

    CHECK(call_cli(aos_run_cli_main,
                   {"aos run", file, "--step", "1"}) == 1);
    CHECK(std::filesystem::is_regular_file(file));
}

TEST_CASE("run_turn 摘要列出非零指令並略過 exit 75") {
    TempDir dir;
    const Layout layout = layout_of(dir.path);
    std::string error;
    REQUIRE(ensure_layout(layout, error));
    write_every(layout, "broken", "[\"/definitely/not/here\"]");
    write_every(layout, "waiting", "[\"sh\",\"-c\",\"exit 75\"]");

    TurnSummary summary;
    REQUIRE(run_turn(layout, summary, error));

    REQUIRE(summary.failures.size() == 1);
    CHECK(summary.failures[0].id == "broken-1");
    CHECK(summary.failures[0].exit == 127);
    CHECK(summary.failures[0].signal == 0);
    CHECK(summary.failures[0].argv0 == "/definitely/not/here");
}

TEST_CASE("aos run 只要有指令失敗就回傳非零") {
    TempDir dir;
    ScopedAosFolder environment(dir.path);
    const Layout layout = layout_of(dir.path);
    std::string error;
    REQUIRE(ensure_layout(layout, error));
    write_every(layout, "broken", "[\"/definitely/not/here\"]");

    CHECK(call_cli(aos_run_cli_main,
                   {"aos run", dir.path, "--step", "1"}) == 1);
}

TEST_CASE("aos run 拒絕已被另一個 runner 鎖住的世界") {
    TempDir dir;
    ScopedAosFolder environment(dir.path);
    const Layout layout = layout_of(dir.path);
    std::string error;
    REQUIRE(ensure_layout(layout, error));
    const std::string lock_path = layout.aos + "/run.lock";
    const int lock_fd = ::open(lock_path.c_str(), O_CREAT | O_RDWR, 0644);
    REQUIRE(lock_fd >= 0);
    REQUIRE(::flock(lock_fd, LOCK_EX | LOCK_NB) == 0);

    CHECK(call_cli(aos_run_cli_main,
                   {"aos run", dir.path, "--step", "1"}) == 1);

    CHECK(::flock(lock_fd, LOCK_UN) == 0);
    CHECK(::close(lock_fd) == 0);
    CHECK(read_turn(layout) == 1);
}

TEST_CASE("aos run 的重複旗標以第一個為準，help 在任意位置都成功") {
    TempDir dir;
    ScopedAosFolder environment(dir.path);

    /* 重複旗標：講出來、以第一個為準，所以這裡只推進 1 回合（不是 2）。 */
    CHECK(call_cli(aos_run_cli_main,
                   {"aos run", "--step", "1", "--step", "2"}) == 0);
    CHECK(read_turn(layout_of(dir.path)) == 2);
    CHECK(call_cli(aos_run_cli_main,
                   {"aos run", "--interval", "1", "--interval", "2"}) == 0);
    CHECK(call_cli(aos_run_cli_main,
                   {"aos run", "--step", "壞值", "--help"}) == 0);
    CHECK(call_cli(aos_run_cli_main, {"aos run", "--nope", "1"}) == 2);
}

TEST_CASE("aos deliver 的 help 在任意位置都成功") {
    TempDir dir;
    ScopedAosFolder environment(dir.path);

    CHECK(call_cli(aos_deliver_cli_main, {"aos deliver", "--help"}) == 0);
    CHECK(call_cli(aos_deliver_cli_main, {"aos deliver", "-h"}) == 0);
    /* `--` 之後的 --help 屬於被投遞的指令，要真的被投出去。 */
    CHECK(call_cli(aos_deliver_cli_main,
                   {"aos deliver", "--", "echo", "--help"}) == 0);
    CHECK(json_files(layout_of(dir.path).inbox).size() == 1);
}
