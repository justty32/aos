#include <aos/tick.hpp>

#include <charconv>
#include <chrono>
#include <iomanip>
#include <limits>
#include <sstream>
#include <system_error>

namespace aos::tick {
namespace {

using Seconds = std::chrono::seconds;
using SysSeconds = std::chrono::sys_time<Seconds>;
using LocalSeconds = std::chrono::local_time<Seconds>;

bool digits(std::string_view text, std::size_t offset, std::size_t count,
            int &value) {
    if (offset + count > text.size()) return false;
    const char *first = text.data() + offset;
    const char *last = first + count;
    for (const char *cursor = first; cursor != last; ++cursor) {
        if (*cursor < '0' || *cursor > '9') return false;
    }
    const auto result = std::from_chars(first, last, value);
    return result.ec == std::errc{} && result.ptr == last;
}

bool read_local(std::string_view text, bool with_seconds, char separator,
                LocalTime &local) {
    const std::size_t expected = with_seconds ? 19 : 16;
    if (text.size() != expected || text[4] != '-' || text[7] != '-' ||
        text[10] != separator || text[13] != ':' ||
        (with_seconds && text[16] != ':')) {
        return false;
    }
    if (!digits(text, 0, 4, local.year) ||
        !digits(text, 5, 2, local.month) ||
        !digits(text, 8, 2, local.day) ||
        !digits(text, 11, 2, local.hour) ||
        !digits(text, 14, 2, local.minute) ||
        (with_seconds && !digits(text, 17, 2, local.second))) {
        return false;
    }
    if (!with_seconds) local.second = 0;
    const std::chrono::year_month_day date{
        std::chrono::year{local.year},
        std::chrono::month{static_cast<unsigned>(local.month)},
        std::chrono::day{static_cast<unsigned>(local.day)}};
    return date.ok() && local.hour >= 0 && local.hour <= 23 &&
           local.minute >= 0 && local.minute <= 59 && local.second >= 0 &&
           local.second <= 59;
}

LocalSeconds local_point(const LocalTime &local) {
    const std::chrono::year_month_day date{
        std::chrono::year{local.year},
        std::chrono::month{static_cast<unsigned>(local.month)},
        std::chrono::day{static_cast<unsigned>(local.day)}};
    return std::chrono::local_days{date} + std::chrono::hours{local.hour} +
           std::chrono::minutes{local.minute} + Seconds{local.second};
}

void split_local(LocalSeconds point, LocalTime &local) {
    const auto day = std::chrono::floor<std::chrono::days>(point);
    const std::chrono::year_month_day date{day};
    const std::chrono::hh_mm_ss clock{point - day};
    local.year = static_cast<int>(date.year());
    local.month = static_cast<unsigned>(date.month());
    local.day = static_cast<unsigned>(date.day());
    local.hour = static_cast<int>(clock.hours().count());
    local.minute = static_cast<int>(clock.minutes().count());
    local.second = static_cast<int>(clock.seconds().count());
    local.weekday = std::chrono::weekday{day}.iso_encoding();
}

std::string clock_error(const std::string &tz, const std::exception &exception) {
    return "時區「" + tz + "」換算失敗：" + exception.what();
}

std::string format_local(const LocalTime &local, bool with_seconds,
                         char separator) {
    std::ostringstream out;
    out << std::setfill('0') << std::setw(4) << local.year << '-'
        << std::setw(2) << local.month << '-' << std::setw(2) << local.day
        << separator << std::setw(2) << local.hour << ':' << std::setw(2)
        << local.minute;
    if (with_seconds) out << ':' << std::setw(2) << local.second;
    return out.str();
}

std::string format_offset(Seconds offset) {
    std::int64_t value = offset.count();
    const char sign = value < 0 ? '-' : '+';
    if (value < 0) value = -value;
    const auto total_minutes = value / 60;
    std::ostringstream out;
    out << sign << std::setfill('0') << std::setw(2) << total_minutes / 60
        << ':' << std::setw(2) << total_minutes % 60;
    return out.str();
}

}  // namespace

bool parse_duration(std::string_view text, std::int64_t &seconds) {
    if (text.size() < 2) return false;
    std::int64_t multiplier = 0;
    switch (text.back()) {
        case 'd': multiplier = 86400; break;
        case 'h': multiplier = 3600; break;
        case 'm': multiplier = 60; break;
        case 's': multiplier = 1; break;
        default: return false;
    }
    std::uint64_t value = 0;
    const auto number = text.substr(0, text.size() - 1);
    const auto result = std::from_chars(number.data(),
                                        number.data() + number.size(), value);
    if (result.ec != std::errc{} || result.ptr != number.data() + number.size() ||
        value == 0 || value > static_cast<std::uint64_t>(
                                  std::numeric_limits<std::int64_t>::max() /
                                  multiplier)) {
        return false;
    }
    seconds = static_cast<std::int64_t>(value) * multiplier;
    return true;
}

bool valid_zone(const std::string &tz) {
    try {
        return std::chrono::locate_zone(tz) != nullptr;
    } catch (...) {
        return false;
    }
}

bool to_local(Instant at, const std::string &tz, LocalTime &local,
              std::string &error) {
    try {
        const auto *zone = std::chrono::locate_zone(tz);
        split_local(zone->to_local(SysSeconds{Seconds{at}}), local);
        error.clear();
        return true;
    } catch (const std::exception &exception) {
        error = clock_error(tz, exception);
    } catch (...) {
        error = "時區「" + tz + "」換算失敗：未知錯誤";
    }
    return false;
}

bool from_local(const LocalTime &local, const std::string &tz, Instant &at,
                std::string &error) {
    const std::chrono::year_month_day date{
        std::chrono::year{local.year},
        std::chrono::month{static_cast<unsigned>(local.month)},
        std::chrono::day{static_cast<unsigned>(local.day)}};
    if (!date.ok() || local.hour < 0 || local.hour > 23 || local.minute < 0 ||
        local.minute > 59 || local.second < 0 || local.second > 59) {
        error = "當地時間不合法";
        return false;
    }
    try {
        const auto *zone = std::chrono::locate_zone(tz);
        const LocalSeconds point = local_point(local);
        SysSeconds resolved;
        try {
            resolved = zone->to_sys(point, std::chrono::choose::earliest);
        } catch (const std::chrono::nonexistent_local_time &) {
            resolved = zone->get_info(point).second.begin;
        }
        at = resolved.time_since_epoch().count();
        error.clear();
        return true;
    } catch (const std::exception &exception) {
        error = clock_error(tz, exception);
    } catch (...) {
        error = "時區「" + tz + "」換算失敗：未知錯誤";
    }
    return false;
}

bool parse_timestamp(std::string_view text, Instant &at) {
    const bool utc = text.size() == 20 && text.back() == 'Z';
    const bool offset = text.size() == 25 &&
                        (text[19] == '+' || text[19] == '-') &&
                        text[22] == ':';
    if (!utc && !offset) return false;
    LocalTime local;
    if (!read_local(text.substr(0, 19), true, 'T', local)) return false;
    int offset_hour = 0;
    int offset_minute = 0;
    if (offset && (!digits(text, 20, 2, offset_hour) ||
                   !digits(text, 23, 2, offset_minute) || offset_hour > 23 ||
                   offset_minute > 59)) {
        return false;
    }
    const auto date = std::chrono::sys_days{
        std::chrono::year{local.year} /
        std::chrono::month{static_cast<unsigned>(local.month)} /
        std::chrono::day{static_cast<unsigned>(local.day)}};
    SysSeconds point = date + std::chrono::hours{local.hour} +
                       std::chrono::minutes{local.minute} + Seconds{local.second};
    std::int64_t shift = offset_hour * 3600 + offset_minute * 60;
    if (offset && text[19] == '-') shift = -shift;
    at = (point - Seconds{shift}).time_since_epoch().count();
    return true;
}

std::string format_timestamp(Instant at, const std::string &tz) {
    try {
        const auto *zone = std::chrono::locate_zone(tz);
        const SysSeconds point{Seconds{at}};
        LocalTime local;
        split_local(zone->to_local(point), local);
        return format_local(local, true, 'T') +
               format_offset(zone->get_info(point).offset);
    } catch (...) {
        return {};
    }
}

bool parse_at(std::string_view text, const std::string &tz, Instant &at) {
    LocalTime local;
    if (!read_local(text, false, ' ', local)) return false;
    std::string error;
    return from_local(local, tz, at, error);
}

std::string format_at(Instant at, const std::string &tz) {
    LocalTime local;
    std::string error;
    return to_local(at, tz, local, error) ? format_local(local, false, ' ') :
                                           std::string{};
}

}  // namespace aos::tick
