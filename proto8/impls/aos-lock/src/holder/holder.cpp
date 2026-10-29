// holder.cpp：【holder】名牌——身分、替行程填名牌、讀鎖、判能不能收；與 common.hpp 的時間、名字小工具（說明見 aos/lock.hpp）。
//
// 判死活照 N-17：pid＋started_at_ticks＋boot_id（同 aos-daemon 的 adopt 看子 loop）；不看 flock（衝突 6：kernel 那套各管各的）。
#include "common/common.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <cerrno>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
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

std::string unique_id() {
    long long ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                       std::chrono::system_clock::now().time_since_epoch()).count();
    std::optional<long long> ticks = aos::proc_started_at_ticks(0);
    char buf[96];
    std::snprintf(buf, sizeof buf, "%020lld.%ld.%lld", ns, (long)getpid(), ticks ? *ticks : -1LL);
    return buf;
}

std::string identity() {
    const char* ws = std::getenv("AOS_WS");
    if (ws != nullptr && ws[0] != '\0') {
        return aos::abspath(ws);
    }
    const char* home = std::getenv("HOME");
    if (home != nullptr && home[0] != '\0') {
        return aos::abspath(home);
    }
    return "/";
}

Holder holder_of(pid_t pid) {
    Holder h;
    h.holder = identity();
    h.pid = pid == 0 ? (long long)getpid() : (long long)pid;
    h.started_at_ticks = aos::proc_started_at_ticks(pid);
    h.boot_id = aos::boot_id();
    h.acquired_at = aos::utc_now_ms();
    return h;
}

Json to_json(const Holder& h) {
    Json j = Json::object();
    j["holder"] = h.holder;
    j["pid"] = h.pid;
    j["started_at_ticks"] = h.started_at_ticks ? Json(*h.started_at_ticks) : Json();
    j["boot_id"] = h.boot_id ? Json(*h.boot_id) : Json();
    j["acquired_at"] = h.acquired_at;
    if (h.lease_ms) {
        j["lease_ms"] = *h.lease_ms;
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
    return s;
}

static bool is_int(const Json& j, const char* key) {
    return j.contains(key) && j[key].is_number_integer();
}

// /proc/<pid>/stat 第 3 欄（狀態）是 Z（殭屍）或 X（正在消失）。讀不到＝不算（上面已經看過在不在）。
static bool zombie(pid_t pid) {
    int err = 0;
    std::optional<std::string> text = aos::read_file("/proc/" + std::to_string(pid) + "/stat", err);
    if (!text) {
        return false;
    }
    size_t close_paren = text->rfind(')');
    if (close_paren == std::string::npos || close_paren + 2 >= text->size()) {
        return false;
    }
    char state = (*text)[close_paren + 2];
    return state == 'Z' || state == 'X';
}

bool reapable(const Seen& s) {
    if (!s.held) {
        return false;
    }
    if (!s.holder || !is_int(*s.holder, "pid")) {
        return s.age_ms >= STALE_MS;   // 名牌還沒寫好就死了、或讀不懂
    }
    const Json& j = *s.holder;
    // 1. 開機過了：舊名牌上的行程都不在了
    std::optional<std::string> boot = aos::boot_id();
    if (j.contains("boot_id") && j["boot_id"].is_string() && boot && j["boot_id"].get<std::string>() != *boot) {
        return true;
    }
    // 2. pid＋started_at_ticks
    long long pid = j["pid"].get<long long>();
    if (pid <= 0) {
        return true;
    }
    if (is_int(j, "started_at_ticks")) {
        std::optional<long long> now = aos::proc_started_at_ticks((pid_t)pid);
        if (!now || *now != j["started_at_ticks"].get<long long>()) {
            return true;
        }
    } else if (kill((pid_t)pid, 0) != 0 && errno == ESRCH) {
        return true;
    }
    if (zombie((pid_t)pid)) {
        return true;   // 已經結束、只是父行程還沒收屍：/proc 還在、ticks 也對得上，但它不會再放鎖了
    }
    // 3. 租約到期
    if (is_int(j, "lease_ms") && j.contains("acquired_at") && j["acquired_at"].is_string()) {
        std::optional<long long> at = parse_at(j["acquired_at"].get<std::string>());
        if (at && now_ms() > *at + j["lease_ms"].get<long long>()) {
            return true;
        }
    }
    return false;
}

}  // namespace aos::lock
