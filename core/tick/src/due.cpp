#include <aos/tick.hpp>

#include <chrono>
#include <limits>
#include <tuple>
#include <utility>

namespace aos::tick {
namespace {

bool run_is_empty(const Run &run) {
    return run.argv.empty() && run.ask.empty();
}

auto date_key(const LocalTime &local) {
    return std::tuple{local.year, local.month, local.day};
}

std::uint64_t elapsed(Instant later, Instant earlier) {
    return static_cast<std::uint64_t>(later) -
           static_cast<std::uint64_t>(earlier);
}

bool read_last_date(const Routine &routine, const std::string &tz,
                    LocalTime &last_local, std::string &error) {
    Instant last = 0;
    if (!parse_timestamp(routine.last_run, last)) {
        error = "last_run 不是合法時間戳: " + routine.last_run;
        return false;
    }
    if (!to_local(last, tz, last_local, error)) {
        error = "last_run 無法換算為當地時間: " + error;
        return false;
    }
    return true;
}

}  // namespace

bool parse_slot(std::string_view text, SlotSpec &spec) {
    if (text.size() != 5 && text.size() != 13) return false;
    if (text[2] != ':' || (text.size() == 13 && text[5] != ' ')) {
        return false;
    }
    for (const std::size_t index : {0U, 1U, 3U, 4U}) {
        if (text[index] < '0' || text[index] > '9') return false;
    }

    const int hour = (text[0] - '0') * 10 + (text[1] - '0');
    const int minute = (text[3] - '0') * 10 + (text[4] - '0');
    if (hour > 23 || minute > 59) return false;

    SlotSpec parsed;
    parsed.hour = hour;
    parsed.minute = minute;
    parsed.days.fill(true);
    if (text.size() == 13) {
        for (std::size_t index = 0; index < parsed.days.size(); ++index) {
            const char marker = text[6 + index];
            if (marker != '1' && marker != '.') return false;
            parsed.days[index] = marker == '1';
        }
    }
    spec = parsed;
    return true;
}

bool routine_due(const Routine &routine, Instant now, const std::string &tz,
                 std::string &error) {
    error.clear();
    if (run_is_empty(routine.run)) {
        error = "run 欄是空的（既沒有 argv 也沒有 ask）";
        return false;
    }

    if (routine.kind == "interval") {
        std::int64_t every = 0;
        if (!parse_duration(routine.every, every)) {
            error = "every 不是合法期間: " + routine.every;
            return false;
        }
        if (routine.last_run.empty()) return true;

        Instant last = 0;
        if (!parse_timestamp(routine.last_run, last)) {
            error = "last_run 不是合法時間戳: " + routine.last_run;
            return false;
        }
        return now >= last &&
               elapsed(now, last) >= static_cast<std::uint64_t>(every);
    }

    if (routine.kind == "slot") {
        SlotSpec slot;
        if (!parse_slot(routine.slot, slot)) {
            error = "slot 不是 HH:MM 或 HH:MM 遮罩: " + routine.slot;
            return false;
        }
        LocalTime local;
        if (!to_local(now, tz, local, error)) {
            error = "now 無法換算為當地時間: " + error;
            return false;
        }

        bool earlier_date = routine.last_run.empty();
        if (!routine.last_run.empty()) {
            LocalTime last_local;
            if (!read_last_date(routine, tz, last_local, error)) return false;
            earlier_date = date_key(last_local) < date_key(local);
        }
        return slot.days[static_cast<std::size_t>(local.weekday - 1)] &&
               std::pair{local.hour, local.minute} >=
                   std::pair{slot.hour, slot.minute} &&
               earlier_date;
    }

    error = "kind 不是 interval 或 slot: " + routine.kind;
    return false;
}

std::optional<Instant> routine_next(const Routine &routine, Instant now,
                                    const std::string &tz) {
    std::string error;
    if (routine_due(routine, now, tz, error) || !error.empty()) {
        return std::nullopt;
    }

    if (routine.kind == "interval") {
        std::int64_t every = 0;
        Instant last = 0;
        if (!parse_duration(routine.every, every) ||
            !parse_timestamp(routine.last_run, last)) {
            return std::nullopt;
        }
        if (last > std::numeric_limits<Instant>::max() - every) {
            return std::nullopt;
        }
        return last + every;
    }

    SlotSpec slot;
    LocalTime local;
    if (!parse_slot(routine.slot, slot) ||
        !to_local(now, tz, local, error)) {
        return std::nullopt;
    }

    std::optional<std::tuple<int, int, int>> last_date;
    if (!routine.last_run.empty()) {
        LocalTime last_local;
        if (!read_last_date(routine, tz, last_local, error)) {
            return std::nullopt;
        }
        last_date = date_key(last_local);
    }

    using namespace std::chrono;
    const sys_days first{year{local.year} /
                         month{static_cast<unsigned>(local.month)} /
                         day{static_cast<unsigned>(local.day)}};
    for (int offset = 0; offset <= 7; ++offset) {
        const year_month_day date{first + days{offset}};
        LocalTime candidate;
        candidate.year = static_cast<int>(date.year());
        candidate.month = static_cast<unsigned>(date.month());
        candidate.day = static_cast<unsigned>(date.day());
        candidate.hour = slot.hour;
        candidate.minute = slot.minute;
        const sys_days candidate_day = sys_days{date};
        const weekday weekday_value{candidate_day};
        const int iso_weekday = weekday_value.iso_encoding();
        if (!slot.days[static_cast<std::size_t>(iso_weekday - 1)]) continue;
        if (last_date && date_key(candidate) <= *last_date) continue;

        Instant result = 0;
        if (!from_local(candidate, tz, result, error)) return std::nullopt;
        if (result > now) return result;
    }
    return std::nullopt;
}

ScheduleState schedule_state(const ScheduleItem &item, Instant now,
                             const Config &config, std::string &error) {
    error.clear();
    if (run_is_empty(item.run)) {
        error = "run 欄是空的（既沒有 argv 也沒有 ask）";
        return ScheduleState::pending;
    }

    Instant at = 0;
    if (!parse_at(item.at, config.tz, at)) {
        error = "at 不是 YYYY-MM-DD HH:MM: " + item.at;
        return ScheduleState::pending;
    }
    std::int64_t missed_after = 0;
    if (!parse_duration(config.missed_after, missed_after)) {
        error = "missed_after 不是合法期間: " + config.missed_after;
        return ScheduleState::pending;
    }
    if (at > now) return ScheduleState::pending;
    if (elapsed(now, at) <= static_cast<std::uint64_t>(missed_after)) {
        return ScheduleState::due;
    }
    return ScheduleState::missed;
}

}  // namespace aos::tick
