// holder.cpp：【holder】名牌與 flock 存活快照、兩鐘租約判斷。
#include "common/common.hpp"

#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"
#include "aos/util/clock.hpp"
#include <fcntl.h>
#include <sys/file.h>
#include <limits>

#include <cerrno>
#include <chrono>
#include <cstdio>
#include <ctime>

#include <sys/stat.h>
#include <unistd.h>

namespace aos::lock {

long long now_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::system_clock::now().time_since_epoch()).count();
}

std::optional<long long> parse_at(const std::string& at) {
    int y = 0, mo = 0, d = 0, h = 0, mi = 0, s = 0, ms = 0, used = 0;
    if (std::sscanf(at.c_str(), "%4d-%2d-%2dT%2d:%2d:%2d.%3d%n", &y, &mo, &d, &h, &mi, &s, &ms, &used) != 7) {
        return std::nullopt;
    }
    std::string zone = at.substr((size_t)used);
    if (zone != "+00:00" && zone != "Z") {
        return std::nullopt;
    }
    std::tm tm{};
    tm.tm_year = y - 1900;
    tm.tm_mon = mo - 1;
    tm.tm_mday = d;
    tm.tm_hour = h;
    tm.tm_min = mi;
    tm.tm_sec = s;
    return (long long)timegm(&tm) * 1000LL + ms;
}

Holder holder_of(bool flock) {
    Holder h;
    h.holder = aos::identity();
    h.flock = flock;
    h.acquired_at = aos::utc_now_ms();
    h.acquired_at_cycles = aos::now_cycle();
    return h;
}

Json to_json(const Holder& h) {
    Json j = {{"holder", h.holder}, {"acquired_at", h.acquired_at}};
    if (h.flock) {
        j["flock"] = true;
    }
    if (h.acquired_at_cycles) {
        j["acquired_at_cycles"] = *h.acquired_at_cycles;
    }
    if (h.lease_cycles) {
        j["lease_cycles"] = *h.lease_cycles;
    }
    if (h.note) {
        j["note"] = *h.note;
    }
    return j;
}

Seen look(const std::string& lock_dir) {
    Seen s;
    struct stat st{};
    if (stat(lock_dir.c_str(), &st) != 0 || !S_ISDIR(st.st_mode)) {
        return s;
    }
    s.held = true;
    s.ino = (unsigned long long)st.st_ino;
    long long mtime_ms = (long long)st.st_mtim.tv_sec * 1000LL + st.st_mtim.tv_nsec / 1000000L;
    s.age_ms = now_ms() - mtime_ms;
    int err = 0;
    s.raw = aos::read_file(aos::join(lock_dir, "holder.json"), err);
    if (s.raw) {
        try {
            Json j = Json::parse(*s.raw);
            if (j.is_object()) {
                s.holder = j;
            }
        } catch (const std::exception&) {
        }
    }
    if (s.holder && s.holder->value("flock", Json()) == Json(true)) {
        std::string path = aos::join(lock_dir, "holder.flock");
        int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
        if (fd >= 0) {
            s.alive = true;
            if (flock(fd, LOCK_EX | LOCK_NB) == 0) {
                s.alive = false;
            }
            close(fd);
        } else if (errno == ENOENT) {
            s.alive = false;
        }
    }
    return s;
}

// 只接受可表示的非負數，避免 unsigned JSON 轉 signed 時繞回。
static std::optional<long long> count(const Json& j, const char* key) {
    if (!j.contains(key) || !j[key].is_number_integer()) {
        return std::nullopt;
    }
    if (j[key].is_number_unsigned() && j[key].get<unsigned long long>() >
        static_cast<unsigned long long>(std::numeric_limits<long long>::max())) {
        return std::nullopt;
    }
    long long n = j[key].get<long long>();
    if (n < 0) {
        return std::nullopt;
    }
    return n;
}

bool reapable(const Seen& s) {
    if (!s.held) {
        return false;
    }
    if (!s.holder || !s.holder->value("holder", Json()).is_string() ||
        !s.holder->value("acquired_at", Json()).is_string()) {
        return s.age_ms >= STALE_MS || s.age_ms <= -STALE_MS;
    }
    const Json& j = *s.holder;
    std::optional<long long> at = parse_at(j["acquired_at"].get<std::string>());
    if (!at || (j.contains("lease_cycles") && !count(j, "lease_cycles")) ||
        (j.contains("acquired_at_cycles") && !count(j, "acquired_at_cycles")) ||
        (j.contains("flock") && !j["flock"].is_boolean())) {
        return s.age_ms >= STALE_MS || s.age_ms <= -STALE_MS;
    }
    if (s.alive && !*s.alive) {
        return true;
    }
    std::optional<long long> lease = count(j, "lease_cycles");
    if (!lease) {
        return false;
    }
    std::optional<long long> cycle = aos::now_cycle();
    std::optional<long long> at_cycle = count(j, "acquired_at_cycles");
    if (cycle && at_cycle) {
        return *cycle >= *at_cycle && *cycle - *at_cycle >= *lease;
    }
    // 用寬整數比較，乘法與期限加法都不溢位。
    return static_cast<__int128>(now_ms()) >= static_cast<__int128>(*at) +
        static_cast<__int128>(*lease) * aos::clock_interval_ms();
}

}  // namespace aos::lock
