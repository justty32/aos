#include "test_support.hpp"

#include <utility>

namespace aos::tick::test {
namespace {

constexpr Instant now = 1788141600;  // 2026-08-31 10:00 Asia/Taipei
const std::string tz = "Asia/Taipei";

loop::Layout new_world(TempDir &temp) {
    const loop::Layout layout = make_world(temp.path);
    std::string error;
    REQUIRE(ensure_heartbeat(paths_of(layout), now, tz, error));
    return layout;
}

Routine routine(std::string id, Run run, std::string last_run = {}) {
    Routine row;
    row.id = std::move(id);
    row.kind = "interval";
    row.every = "60s";
    row.last_run = std::move(last_run);
    row.run = std::move(run);
    return row;
}

ScheduleItem item(std::string id, std::string at, Run run) {
    ScheduleItem row;
    row.id = std::move(id);
    row.at = std::move(at);
    row.run = std::move(run);
    return row;
}

TickReport tick(const loop::Layout &layout, std::uint64_t turn = 7,
                bool dry_run = false) {
    TickReport report;
    std::string error;
    REQUIRE(run_tick(layout, now, TickOptions{dry_run, turn}, report, error));
    REQUIRE(error.empty());
    return report;
}

void save_routines(const loop::Layout &layout,
                   const std::vector<Routine> &rows) {
    std::string error;
    REQUIRE(write_routines(paths_of(layout).routines_file, rows, now, tz,
                           error));
}

void save_schedule(const loop::Layout &layout,
                   const std::vector<ScheduleItem> &rows) {
    std::string error;
    REQUIRE(write_schedule(paths_of(layout).schedule_file, rows, now, tz,
                           error));
}

}  // namespace

TEST_CASE("到期 argv 投遞、更新 last_run 並寫 log") {
    TempDir temp;
    const auto layout = new_world(temp);
    save_routines(layout, {routine("job", Run{{"true"}, {}})});

    tick(layout);
    REQUIRE(inbox_ids(layout) == std::vector<std::string>{"hb-job-7"});

    std::vector<Routine> rows;
    std::string error;
    REQUIRE(read_routines(paths_of(layout).routines_file, rows, error));
    REQUIRE(rows.size() == 1);
    REQUIRE_FALSE(rows[0].last_run.empty());
    REQUIRE(read_file(paths_of(layout).log_file).find(
                "run=job→hb-job-7") != std::string::npos);
}

TEST_CASE("未到期時沒有 inbox、log 或 report 行") {
    TempDir temp;
    const auto layout = new_world(temp);
    save_routines(layout,
                  {routine("later", Run{{"true"}, {}},
                           format_timestamp(now, tz))});

    const TickReport report = tick(layout);
    REQUIRE(inbox_ids(layout).empty());
    REQUIRE_FALSE(exists(paths_of(layout).log_file));
    REQUIRE(report.line.empty());
}

TEST_CASE("到點 schedule 投遞後刪列") {
    TempDir temp;
    const auto layout = new_world(temp);
    save_schedule(layout,
                  {item("once", "2026-08-31 09:59", Run{{"true"}, {}})});

    tick(layout, 9);
    REQUIRE(inbox_ids(layout) == std::vector<std::string>{"hb-once-9"});
    std::vector<ScheduleItem> rows;
    std::string error;
    REQUIRE(read_schedule(paths_of(layout).schedule_file, rows, error));
    REQUIRE(rows.empty());
}

TEST_CASE("錯過很久只通知 agent 並刪列") {
    TempDir temp;
    const auto layout = new_world(temp);
    make_agent(layout, "bob");
    save_schedule(layout,
                  {item("late", "2026-08-31 03:00",
                        Run{{"dangerous"}, {}})});

    tick(layout);
    REQUIRE(inbox_ids(layout).empty());
    REQUIRE(say_count(layout, "bob") == 1);
    std::vector<ScheduleItem> rows;
    std::string error;
    REQUIRE(read_schedule(paths_of(layout).schedule_file, rows, error));
    REQUIRE(rows.empty());
    REQUIRE(read_file(paths_of(layout).log_file).find("missed=late→bob") !=
            std::string::npos);
}

TEST_CASE("ask 依 agent 數量選擇 target 並更新 routine") {
    TempDir temp;
    const auto layout = new_world(temp);

    SECTION("沒有 agent") {
        save_routines(layout, {routine("ask0", Run{{}, "請處理"})});
        const TickReport report = tick(layout);
        REQUIRE(report.events[0].target == "none");
        REQUIRE(read_file(paths_of(layout).log_file).find("ask=ask0→none") !=
                std::string::npos);
    }

    SECTION("兩隻 agent") {
        make_agent(layout, "alice");
        make_agent(layout, "bob");
        save_routines(layout, {routine("ask2", Run{{}, "請處理"})});
        const TickReport report = tick(layout);
        REQUIRE(report.events[0].target == "none");
        REQUIRE(say_count(layout, "alice") == 0);
        REQUIRE(say_count(layout, "bob") == 0);
    }

    SECTION("剛好一隻 agent") {
        make_agent(layout, "bob");
        save_routines(layout, {routine("ask1", Run{{}, "請處理"})});
        const TickReport report = tick(layout);
        REQUIRE(report.events[0].target == "bob");
        REQUIRE(say_count(layout, "bob") == 1);
    }

    std::vector<Routine> rows;
    std::string error;
    REQUIRE(read_routines(paths_of(layout).routines_file, rows, error));
    REQUIRE_FALSE(rows[0].last_run.empty());
}

TEST_CASE("dry-run 有計畫但完全沒有副作用") {
    TempDir temp;
    const auto layout = new_world(temp);
    save_routines(layout, {routine("preview", Run{{"true"}, {}})});

    const TickReport report = tick(layout, 12, true);
    REQUIRE_FALSE(report.events.empty());
    REQUIRE_FALSE(report.line.empty());
    REQUIRE(inbox_ids(layout).empty());
    REQUIRE_FALSE(exists(paths_of(layout).log_file));

    std::vector<Routine> rows;
    std::string error;
    REQUIRE(read_routines(paths_of(layout).routines_file, rows, error));
    REQUIRE(rows[0].last_run.empty());
}

TEST_CASE("agent 尚未初始化時 say 例外轉成 error 且不更新") {
    TempDir temp;
    const auto layout = new_world(temp);
    std::filesystem::create_directories(
        std::filesystem::path(layout.agents_dir) / "bob");
    save_routines(layout, {routine("broken", Run{{}, "請處理"})});

    const TickReport report = tick(layout);
    REQUIRE(report.events.size() == 1);
    REQUIRE(report.events[0].kind == "error");
    std::vector<Routine> rows;
    std::string error;
    REQUIRE(read_routines(paths_of(layout).routines_file, rows, error));
    REQUIRE(rows[0].last_run.empty());
}

TEST_CASE("無效 routine 記 error 但保留列並完成心跳") {
    TempDir temp;
    const auto layout = new_world(temp);
    Routine bad = routine("bad", Run{{"true"}, {}});
    bad.kind = "weird";
    save_routines(layout, {bad});

    const TickReport report = tick(layout);
    REQUIRE(report.events.size() == 1);
    REQUIRE(report.events[0].kind == "error");
    std::vector<Routine> rows;
    std::string error;
    REQUIRE(read_routines(paths_of(layout).routines_file, rows, error));
    REQUIRE(rows.size() == 1);
    REQUIRE(rows[0].kind == "weird");
}

TEST_CASE("format_log_line 處理空事件與兩個箭頭") {
    REQUIRE(format_log_line(now, tz, 3, {}).empty());
    const std::string line = format_log_line(
        now, tz, 3, {{"run", "a", "x"}, {"error", "b", "壞\n掉\r"}});
    REQUIRE(line.find("turn=3") != std::string::npos);
    REQUIRE(std::count(line.begin(), line.end(), '\n') == 1);
    REQUIRE(line.ends_with('\n'));
    REQUIRE(line.find("run=a→x") != std::string::npos);
    REQUIRE(line.find("error=b→壞 掉 ") != std::string::npos);
    std::size_t arrows = 0;
    for (std::size_t position = 0;
         (position = line.find("→", position)) != std::string::npos;
         position += std::string("→").size()) {
        ++arrows;
    }
    REQUIRE(arrows == 2);
}

}  // namespace aos::tick::test
