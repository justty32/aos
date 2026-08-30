#define _POSIX_C_SOURCE 200809L

#include <aos/exec.hpp>

#include "clock.hpp"

#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <limits>
#include <string>

#include <time.h>

namespace aos::exec {

std::string now_iso8601() {
    timespec value{};
    if (clock_gettime(CLOCK_REALTIME, &value) != 0) {
        return {};
    }

    std::tm utc{};
    if (gmtime_r(&value.tv_sec, &utc) == nullptr) {
        return {};
    }

    char buffer[32];
    const int length = std::snprintf(
        buffer, sizeof(buffer), "%04d-%02d-%02dT%02d:%02d:%02d.%03ldZ",
        utc.tm_year + 1900, utc.tm_mon + 1, utc.tm_mday, utc.tm_hour,
        utc.tm_min, utc.tm_sec, value.tv_nsec / 1000000L);
    if (length < 0 || static_cast<std::size_t>(length) >= sizeof(buffer)) {
        return {};
    }
    return std::string(buffer, static_cast<std::size_t>(length));
}

namespace detail {

std::uint64_t monotonic_ms() {
    timespec value{};
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) {
        return 0;
    }
    const auto seconds = static_cast<std::uint64_t>(value.tv_sec);
    if (seconds > std::numeric_limits<std::uint64_t>::max() / 1000) {
        return std::numeric_limits<std::uint64_t>::max();
    }
    return seconds * 1000 + static_cast<std::uint64_t>(value.tv_nsec / 1000000L);
}

void sleep_ms(std::uint64_t milliseconds) {
    timespec request{
        static_cast<time_t>(milliseconds / 1000),
        static_cast<long>((milliseconds % 1000) * 1000000),
    };
    timespec remaining{};
    while (nanosleep(&request, &remaining) < 0 && errno == EINTR) {
        request = remaining;
    }
}

}  // namespace detail
}  // namespace aos::exec
