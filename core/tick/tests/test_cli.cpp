#include "test_support.hpp"

#include <nlohmann/json.hpp>

#include <string>
#include <vector>

extern "C" int aos_tick_cli_main(int, char **);
extern "C" int aos_heartbeat_cli_main(int, char **);
extern "C" int aos_routine_cli_main(int, char **);
extern "C" int aos_schedule_cli_main(int, char **);

namespace aos::tick::test {
namespace {

using Entry = int (*)(int, char **);

int invoke(Entry entry, std::vector<std::string> words) {
    std::vector<char *> argv;
    argv.reserve(words.size());
    for (auto &word : words) argv.push_back(word.data());
    return entry(static_cast<int>(argv.size()), argv.data());
}

}  // namespace

TEST_CASE("heartbeat init 建立心跳檔與空表") {
    TempDir world;
    CHECK(invoke(aos_heartbeat_cli_main,
                 {"aos heartbeat", "init", world.path, "--interval", "1s"}) == 0);

    const auto layout = loop::layout_of(world.path);
    const auto tick_json = nlohmann::json::parse(read_file(layout.every + "/tick.json"));
    CHECK(tick_json.at("every_ms") == 1000);
    CHECK(tick_json.at("argv") == nlohmann::json::array({"aos", "tick"}));
    const auto paths = paths_of(layout);
    CHECK(exists(paths.routines_file));
    CHECK(exists(paths.schedule_file));
}

TEST_CASE("routine CLI 可新增列出並拒絕缺少執行內容") {
    TempDir world;
    CHECK(invoke(aos_routine_cli_main,
                 {"aos routine", "add", world.path, "--every", "2s", "--", "true"}) == 0);
    CHECK(invoke(aos_routine_cli_main,
                 {"aos routine", "ls", world.path}) == 0);

    std::vector<Routine> rows;
    std::string error;
    CHECK(read_routines(paths_of(loop::layout_of(world.path)).routines_file,
                        rows, error));
    REQUIRE(rows.size() == 1);
    CHECK(rows[0].kind == "interval");
    CHECK(rows[0].every == "2s");
    CHECK(invoke(aos_routine_cli_main,
                 {"aos routine", "add", world.path, "--every", "2s"}) == 2);
}

TEST_CASE("routine add 驗證期間、模式與重複 id") {
    TempDir world;
    CHECK(invoke(aos_routine_cli_main,
                 {"aos routine", "add", world.path, "--every", "2s",
                  "--slot", "09:30", "--", "true"}) == 2);
    CHECK(invoke(aos_routine_cli_main,
                 {"aos routine", "add", world.path, "--every", "1h30m",
                  "--", "true"}) == 2);
    const std::vector<std::string> command = {
        "aos routine", "add", world.path, "--every", "2s", "--id", "dup",
        "--", "true"};
    CHECK(invoke(aos_routine_cli_main, command) == 0);
    CHECK(invoke(aos_routine_cli_main, command) == 2);
}

TEST_CASE("routine rm 區分不存在與成功移除") {
    TempDir world;
    CHECK(invoke(aos_routine_cli_main,
                 {"aos routine", "rm", world.path, "nosuch"}) == 1);
    CHECK(invoke(aos_routine_cli_main,
                 {"aos routine", "add", world.path, "--every", "2s", "--id",
                  "gone", "--", "true"}) == 0);
    CHECK(invoke(aos_routine_cli_main,
                 {"aos routine", "rm", world.path, "gone"}) == 0);
    std::vector<Routine> rows;
    std::string error;
    CHECK(read_routines(paths_of(loop::layout_of(world.path)).routines_file,
                        rows, error));
    CHECK(rows.empty());
}

TEST_CASE("schedule add 接受固定格式並拒絕寬鬆日期") {
    TempDir world;
    CHECK(invoke(aos_schedule_cli_main,
                 {"aos schedule", "add", world.path, "--at",
                  "2026-09-01 17:00", "--", "true"}) == 0);
    CHECK(invoke(aos_schedule_cli_main,
                 {"aos schedule", "add", world.path, "--at",
                  "2026-9-1 17:00", "--", "true"}) == 2);
}

TEST_CASE("tick dry-run 不投遞已到期 routine") {
    TempDir world;
    CHECK(invoke(aos_routine_cli_main,
                 {"aos routine", "add", world.path, "--every", "2s", "--id",
                  "dry", "--", "true"}) == 0);
    const auto layout = loop::layout_of(world.path);
    CHECK(inbox_ids(layout).empty());
    CHECK(invoke(aos_tick_cli_main,
                 {"aos tick", world.path, "--dry-run"}) == 0);
    CHECK(inbox_ids(layout).empty());
}

}  // namespace aos::tick::test
