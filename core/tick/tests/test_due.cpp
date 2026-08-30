#include "test_support.hpp"

#include <utility>

namespace aos::tick::test {
namespace {

constexpr Instant monday_ten = 1788141600;  // 2026-08-31 10:00 Asia/Taipei
const std::string tz = "Asia/Taipei";

Routine interval_routine() {
    Routine routine;
    routine.id = "interval";
    routine.kind = "interval";
    routine.every = "60s";
    routine.run.argv = {"true"};
    return routine;
}

Routine slot_routine(std::string slot) {
    Routine routine;
    routine.id = "slot";
    routine.kind = "slot";
    routine.slot = std::move(slot);
    routine.run.argv = {"true"};
    return routine;
}

ScheduleItem scheduled(std::string at) {
    ScheduleItem item;
    item.id = "schedule";
    item.at = std::move(at);
    item.run.argv = {"true"};
    return item;
}

}  // namespace

TEST_CASE("interval 以大於等於判定到期") {
    std::string error;
    Routine routine = interval_routine();

    REQUIRE(routine_due(routine, monday_ten, tz, error));
    REQUIRE(error.empty());

    routine.last_run = format_timestamp(monday_ten - 60, tz);
    REQUIRE(routine_due(routine, monday_ten, tz, error));
    REQUIRE(error.empty());

    routine.last_run = format_timestamp(monday_ten - 59, tz);
    REQUIRE_FALSE(routine_due(routine, monday_ten, tz, error));
    REQUIRE(error.empty());
}

TEST_CASE("interval 拒絕複合期間") {
    Routine routine = interval_routine();
    routine.every = "1h30m";
    std::string error;
    REQUIRE_FALSE(routine_due(routine, monday_ten, tz, error));
    REQUIRE_FALSE(error.empty());
}

TEST_CASE("parse_slot 解析每天與平日遮罩") {
    SlotSpec spec;
    REQUIRE(parse_slot("09:30", spec));
    REQUIRE(spec.hour == 9);
    REQUIRE(spec.minute == 30);
    REQUIRE(std::all_of(spec.days.begin(), spec.days.end(),
                        [](bool enabled) { return enabled; }));

    REQUIRE(parse_slot("09:30 11111..", spec));
    const std::array<bool, 7> weekdays = {
        true, true, true, true, true, false, false};
    REQUIRE(spec.days == weekdays);
}

TEST_CASE("parse_slot 拒絕錯誤長度、字元與時間") {
    SlotSpec spec;
    REQUIRE_FALSE(parse_slot("09:30 11111.", spec));
    REQUIRE_FALSE(parse_slot("09:30 11111111", spec));
    REQUIRE_FALSE(parse_slot("09:30 1111x..", spec));
    REQUIRE_FALSE(parse_slot("24:00", spec));
    REQUIRE_FALSE(parse_slot("09:60", spec));
}

TEST_CASE("slot 同時檢查星期、時間與一天一次") {
    std::string error;

    Routine routine = slot_routine("09:30 .1.....");
    REQUIRE_FALSE(routine_due(routine, monday_ten, tz, error));
    REQUIRE(error.empty());

    routine.slot = "10:01 1......";
    REQUIRE_FALSE(routine_due(routine, monday_ten, tz, error));
    REQUIRE(error.empty());

    routine.slot = "09:30 1......";
    REQUIRE(routine_due(routine, monday_ten, tz, error));

    routine.last_run = "2026-08-31T09:00:00+08:00";
    REQUIRE_FALSE(routine_due(routine, monday_ten, tz, error));
    REQUIRE(error.empty());

    routine.last_run = "2026-08-30T23:59:00+08:00";
    REQUIRE(routine_due(routine, monday_ten, tz, error));
}

TEST_CASE("routine_next 回傳未到期 interval 的精確時刻") {
    Routine routine = interval_routine();
    routine.last_run = format_timestamp(monday_ten, tz);
    REQUIRE(routine_next(routine, monday_ten, tz) == monday_ten + 60);

    routine.last_run = format_timestamp(monday_ten - 60, tz);
    REQUIRE_FALSE(routine_next(routine, monday_ten, tz).has_value());
}

TEST_CASE("routine_next 尋找下一個允許的 slot 日期") {
    Routine routine = slot_routine("09:30 .1.....");
    const auto next = routine_next(routine, monday_ten, tz);
    REQUIRE(next.has_value());
    REQUIRE(*next > monday_ten);
    REQUIRE(format_at(*next, tz) == "2026-09-01 09:30");
}

TEST_CASE("schedule_state 涵蓋三態與六小時邊界") {
    const Config config;
    std::string error;

    REQUIRE(schedule_state(scheduled("2026-08-31 10:01"), monday_ten,
                           config, error) == ScheduleState::pending);
    REQUIRE(error.empty());
    REQUIRE(schedule_state(scheduled("2026-08-31 09:59"), monday_ten,
                           config, error) == ScheduleState::due);
    REQUIRE(schedule_state(scheduled("2026-08-31 03:00"), monday_ten,
                           config, error) == ScheduleState::missed);
    REQUIRE(schedule_state(scheduled("2026-08-31 04:00"), monday_ten,
                           config, error) == ScheduleState::due);

    REQUIRE(schedule_state(scheduled("不是時間"), monday_ten, config,
                           error) == ScheduleState::pending);
    REQUIRE_FALSE(error.empty());
}

}  // namespace aos::tick::test
