#include "test_support.hpp"

#include <filesystem>
#include <string>
#include <vector>

namespace aos::tick::test {
namespace {

void require_same(const Routine &left, const Routine &right) {
    REQUIRE(left.id == right.id);
    REQUIRE(left.kind == right.kind);
    REQUIRE(left.every == right.every);
    REQUIRE(left.slot == right.slot);
    REQUIRE(left.last_run == right.last_run);
    REQUIRE(left.run.argv == right.run.argv);
    REQUIRE(left.run.ask == right.run.ask);
    REQUIRE(left.note == right.note);
}

}  // namespace

TEST_CASE("循環表空表與兩種 run 都能往返") {
    TempDir temp;
    const std::string path = temp.path + "/heartbeat/routines.json";
    std::string error;
    std::vector<Routine> rows;
    REQUIRE(write_routines(path, rows, 1788080400, "Asia/Taipei", error));
    REQUIRE(read_file(path).find("\"contract\": \"wf-table/1\"") !=
            std::string::npos);
    std::vector<Routine> loaded;
    REQUIRE(read_routines(path, loaded, error));
    REQUIRE(loaded.empty());

    Routine argv;
    argv.id = "lint";
    argv.kind = "interval";
    argv.every = "30m";
    argv.last_run = "2026-08-30T16:30:00+08:00";
    argv.run.argv = {"sh", "-c", "make test"};
    argv.note = "檢查程式";
    Routine ask;
    ask.id = "standup";
    ask.kind = "slot";
    ask.slot = "09:30 11111..";
    ask.run.ask = "整理今日進度";
    ask.note = "平日";
    rows = {argv, ask};
    REQUIRE(write_routines(path, rows, 1788080400, "Asia/Taipei", error));
    REQUIRE(read_routines(path, loaded, error));
    REQUIRE(loaded.size() == 2);
    require_same(loaded[0], argv);
    require_same(loaded[1], ask);
}

TEST_CASE("讀表補空欄並拒絕壞 JSON 與重複 id") {
    TempDir temp;
    const std::string path = temp.path + "/routines.json";
    std::string error;
    std::vector<Routine> rows;
    write_file(path, R"({"rows":[{"id":"only","run":"壞格式"}]})");
    REQUIRE(read_routines(path, rows, error));
    REQUIRE(rows.size() == 1);
    REQUIRE(rows[0].id == "only");
    REQUIRE(rows[0].kind.empty());
    REQUIRE(rows[0].every.empty());
    REQUIRE(rows[0].slot.empty());
    REQUIRE(rows[0].last_run.empty());
    REQUIRE(rows[0].run.argv.empty());
    REQUIRE(rows[0].run.ask.empty());
    REQUIRE(rows[0].note.empty());

    write_file(path, "{broken");
    REQUIRE_FALSE(read_routines(path, rows, error));
    REQUIRE(error.find(path) != std::string::npos);
    write_file(path, R"({"rows":[{"id":"same"},{"id":"same"}]})");
    REQUIRE_FALSE(read_routines(path, rows, error));
    REQUIRE(error.find("重複") != std::string::npos);
}

TEST_CASE("設定檔使用預設並讀取覆寫") {
    TempDir temp;
    const std::string path = temp.path + "/config.json";
    Config config;
    std::string error;
    REQUIRE(read_config(path, config, error));
    REQUIRE(config.tz == "Asia/Taipei");
    REQUIRE(config.missed_after == "6h");

    write_file(path, R"({"tz":"UTC","missed_after":"2d"})");
    REQUIRE(read_config(path, config, error));
    REQUIRE(config.tz == "UTC");
    REQUIRE(config.missed_after == "2d");
    write_file(path, "[");
    REQUIRE_FALSE(read_config(path, config, error));
}

TEST_CASE("心跳目錄只建立缺少的空表") {
    TempDir temp;
    const loop::Layout layout = make_world(temp.path);
    const Paths paths = paths_of(layout);
    std::string error;
    REQUIRE(ensure_heartbeat(paths, 1788080400, "Asia/Taipei", error));
    REQUIRE(std::filesystem::is_directory(paths.heartbeat));
    REQUIRE(exists(paths.routines_file));
    REQUIRE(exists(paths.schedule_file));
    REQUIRE_FALSE(exists(paths.log_file));
    REQUIRE_FALSE(exists(paths.config_file));
    std::vector<ScheduleItem> schedule;
    REQUIRE(read_schedule(paths.schedule_file, schedule, error));
    REQUIRE(schedule.empty());

    Routine row;
    row.id = "keep";
    row.kind = "interval";
    row.every = "1h";
    row.run.argv = {"true"};
    REQUIRE(write_routines(paths.routines_file, {row}, 1788080400,
                           "Asia/Taipei", error));
    const std::string before = read_file(paths.routines_file);
    REQUIRE(ensure_heartbeat(paths, 1788084000, "Asia/Taipei", error));
    REQUIRE(read_file(paths.routines_file) == before);
}

TEST_CASE("路徑推導與唯一 agent 判定") {
    TempDir temp;
    const loop::Layout layout = make_world(temp.path);
    const Paths paths = paths_of(layout);
    REQUIRE(paths.heartbeat == layout.aos + "/heartbeat");
    REQUIRE(paths.routines_file == paths.heartbeat + "/routines.json");
    REQUIRE(paths.schedule_file == paths.heartbeat + "/schedule.json");
    REQUIRE(paths.log_file == paths.heartbeat + "/log.md");
    REQUIRE(paths.config_file == paths.heartbeat + "/config.json");
    REQUIRE_FALSE(single_agent(layout).has_value());

    write_file(layout.agents_dir + "/ignored.txt", "x");
    std::filesystem::create_directories(layout.agents_dir + "/.hidden");
    make_agent(layout, "bob");
    REQUIRE(single_agent(layout) == "bob");
    make_agent(layout, "alice");
    REQUIRE_FALSE(single_agent(layout).has_value());
}

}  // namespace aos::tick::test
