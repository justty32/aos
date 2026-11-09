// clock.cpp：【aos-util】讀時鐘與標稱間隔，用樹時鐘或 UTC epoch 毫秒計算期限。
#include "aos/util/clock.hpp"
#include "aos/util/error.hpp"
#include "aos/util/files.hpp"
#include "aos/util/io.hpp"

#include <cerrno>
#include <charconv>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <set>
#include <string>
#include <string_view>
#include <utility>

#include <unistd.h>

namespace aos {
namespace {

void warn_missing_clock(const std::string& path) {
    // 輪詢只提醒一次；fork 後是另一個行程，仍應有自己的提醒。
    static std::set<std::pair<pid_t, std::string>> warned;
    if (warned.emplace(::getpid(), path).second) {
        // aos-util 只支援 Linux；用 glibc 的程式名，不把名稱參數加進整條期限 API。
        warn(::program_invocation_short_name, "AOS_CLOCK points to a missing file; treating the clock as 0");
    }
}

long long decimal(std::string_view text, const std::string& source, bool positive) {
    long long value = 0;
    bool digits = !text.empty();
    for (char ch : text) {
        if (ch < '0' || ch > '9') {
            digits = false;
        }
    }
    if (digits) {
        std::from_chars_result result = std::from_chars(text.data(), text.data() + text.size(), value);
        if (result.ec == std::errc{} && (!positive || value > 0)) {
            return value;
        }
    }
    std::string kind = "a non-negative decimal integer";
    if (positive) {
        kind = "a positive decimal integer";
    }
    throw Error{code::ClockBad, source + " must be " + kind + " within signed 64-bit range"};
}

long long add(long long base, long long amount) {
    constexpr long long high = std::numeric_limits<long long>::max();
    constexpr long long low = std::numeric_limits<long long>::min();
    if ((amount > 0 && base > high - amount) || (amount < 0 && base < low - amount)) {
        throw Error{code::ClockBad, "deadline is outside signed 64-bit range"};
    }
    return base + amount;
}

}  // namespace

std::optional<long long> now_cycle() {
    const char* path = std::getenv("AOS_CLOCK");
    if (path == nullptr || path[0] == '\0') {
        return std::nullopt;
    }
    int err = 0;
    std::optional<std::string> text = read_file(path, err);
    if (!text) {
        if (err == ENOENT) {
            warn_missing_clock(path);
            return 0;
        }
        throw Error{code::ClockBad, std::string("cannot read AOS_CLOCK file ") + path + ": " + std::strerror(err)};
    }
    const char* whitespace = " \t\n\r\f\v";
    size_t first = text->find_first_not_of(whitespace);
    if (first == std::string::npos) {
        return 0;
    }
    size_t last = text->find_last_not_of(whitespace);
    return decimal(std::string_view(*text).substr(first, last - first + 1), "AOS_CLOCK file", false);
}

long long clock_interval_ms() {
    const char* value = std::getenv("AOS_CLOCK_INTERVAL");
    if (value == nullptr || value[0] == '\0') {
        return 1000;
    }
    return decimal(value, "AOS_CLOCK_INTERVAL", true);
}

long long utc_now_epoch_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

Deadline deadline_after(long long cycles) {
    std::optional<long long> now = now_cycle();
    if (now) {
        return {true, add(*now, cycles)};
    }
    long long interval = clock_interval_ms();
    if (cycles > std::numeric_limits<long long>::max() / interval ||
        cycles < std::numeric_limits<long long>::min() / interval) {
        throw Error{code::ClockBad, "deadline duration is outside signed 64-bit range"};
    }
    return {false, add(utc_now_epoch_ms(), cycles * interval)};
}

bool expired(const Deadline& deadline) {
    if (deadline.on_clock) {
        std::optional<long long> now = now_cycle();
        // 同一行程不應失去時鐘；若環境被改掉，不把時鐘期限當牆鐘期限。
        return now && *now >= deadline.at;
    }
    return utc_now_epoch_ms() >= deadline.at;
}

}  // namespace aos
