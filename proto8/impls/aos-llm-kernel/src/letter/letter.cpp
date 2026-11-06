// letter.cpp：【letter】信箱的路徑、信件名稱、寄信的人還在不在（sender.flock）、priority、回信（說明見 aos/llm_kernel.hpp）。
#include "aos/llm_kernel.hpp"

#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"

#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <filesystem>

#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>

namespace aos::llm_kernel {

std::string Mailbox::tmp() const { return aos::join(root, "tmp"); }
std::string Mailbox::fresh() const { return aos::join(root, "new"); }
std::string Mailbox::cur() const { return aos::join(root, "cur"); }

int hold_sender(const std::string& letter_dir) {
    std::string path = aos::join(letter_dir, SENDER_FLOCK);
    int fd = open(path.c_str(), O_RDWR | O_CREAT | O_CLOEXEC, 0666);
    if (fd < 0) {
        throw Error{code::WriteFailed, "cannot open " + path + ": " + std::strerror(errno)};
    }
    if (flock(fd, LOCK_EX) != 0) {
        int e = errno;
        close(fd);
        throw Error{code::WriteFailed, "cannot lock " + path + ": " + std::strerror(e)};
    }
    return fd;
}

bool sender_alive(const std::string& letter_dir) {
    std::string path = aos::join(letter_dir, SENDER_FLOCK);
    int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        return false;   // 沒有鎖檔、或 kernel 讀不到（Linux 權限不給＝這封本來也跑不了）
    }
    bool alive = flock(fd, LOCK_SH | LOCK_NB) != 0 && errno == EWOULDBLOCK;
    close(fd);   // 鎖得到的話一關就放掉
    return alive;
}

bool has_sender(const std::string& letter_dir) {
    std::error_code ec;
    return std::filesystem::exists(aos::join(letter_dir, SENDER_FLOCK), ec);
}

static int level_of(const Json& v) {
    if (v.is_null()) {
        return 0;
    }
    if (v.is_string()) {
        std::string s = v.get<std::string>();
        if (s == "low") {
            return -1;
        }
        if (s == "normal") {
            return 0;
        }
        if (s == "high") {
            return 1;
        }
        throw Error{code::PriorityBad, "level must be \"low\", \"normal\", \"high\" or a number, got " + aos::dumps(v)};
    }
    if (v.is_number()) {   // 數字看正負（10-15：<0／0／>0）
        double d = v.get<double>();
        if (d < 0) {
            return -1;
        }
        if (d > 0) {
            return 1;
        }
        return 0;
    }
    throw Error{code::PriorityBad, "level must be \"low\", \"normal\", \"high\" or a number, got " + aos::dumps(v)};
}

// ISO 8601：YYYY-MM-DDTHH:MM:SS[.小數](Z|±HH:MM)，時區一定要寫（不猜本地時間）。
static std::optional<double> parse_iso(const std::string& s) {
    int y = 0, mo = 0, d = 0, h = 0, mi = 0, se = 0, n = 0;
    if (std::sscanf(s.c_str(), "%4d-%2d-%2d%n", &y, &mo, &d, &n) != 3 || n != 10) {
        return std::nullopt;
    }
    if (s.size() < 19 || (s[10] != 'T' && s[10] != 't')) {
        return std::nullopt;
    }
    if (std::sscanf(s.c_str() + 11, "%2d:%2d:%2d%n", &h, &mi, &se, &n) != 3 || n != 8) {
        return std::nullopt;
    }
    size_t i = 19;
    double frac = 0;
    if (i < s.size() && s[i] == '.') {
        size_t j = i + 1;
        double scale = 0.1;
        while (j < s.size() && s[j] >= '0' && s[j] <= '9') {
            frac += (s[j] - '0') * scale;
            scale /= 10;
            ++j;
        }
        if (j == i + 1) {
            return std::nullopt;
        }
        i = j;
    }
    long offset = 0;
    if (i < s.size() && (s[i] == 'Z' || s[i] == 'z') && i + 1 == s.size()) {
        offset = 0;
    } else if (i < s.size() && (s[i] == '+' || s[i] == '-') && i + 6 == s.size() && s[i + 3] == ':') {
        int oh = 0, om = 0;
        if (std::sscanf(s.c_str() + i + 1, "%2d:%2d", &oh, &om) != 2) {
            return std::nullopt;
        }
        offset = (oh * 60L + om) * 60L;
        if (s[i] == '-') {
            offset = -offset;
        }
    } else {
        return std::nullopt;
    }
    if (mo < 1 || mo > 12 || d < 1 || d > 31 || h > 23 || mi > 59 || se > 60) {
        return std::nullopt;
    }
    std::tm tm{};
    tm.tm_year = y - 1900;
    tm.tm_mon = mo - 1;
    tm.tm_mday = d;
    tm.tm_hour = h;
    tm.tm_min = mi;
    tm.tm_sec = se;
    time_t t = timegm(&tm);
    return (double)t - (double)offset + frac;
}

static double deadline_of(const Json& v) {
    if (v.is_number()) {
        double d = v.get<double>();
        if (std::isfinite(d)) {
            return d;
        }
    }
    if (v.is_string()) {
        std::optional<double> t = parse_iso(v.get<std::string>());
        if (t) {
            return *t;
        }
    }
    throw Error{code::PriorityBad, "deadline must be ISO 8601 with a time zone (e.g. 2026-10-24T18:00:00+08:00) or epoch seconds, got " + aos::dumps(v)};
}

Priority parse_priority(const Json& v) {
    Priority p;
    if (v.is_object()) {   // {"level", "deadline", 其他 key（class…）照帶、不管}
        p.level = level_of(v.value("level", Json()));
        Json dl = v.value("deadline", Json());
        if (!dl.is_null()) {
            p.deadline = deadline_of(dl);
        }
        return p;
    }
    if (v.is_null() || v.is_string() || (v.is_number())) {
        p.level = level_of(v);
        return p;
    }
    throw Error{code::PriorityBad, "priority must be \"low\", \"normal\", \"high\", a number or {\"level\", \"deadline\"}, got " + aos::dumps(v)};
}

Priority priority_of(const Json& letter) {
    Json body = letter.value("body", Json());
    if (!body.is_object()) {
        return parse_priority(Json());
    }
    return parse_priority(body.value("priority", Json()));
}

std::optional<Json> reply_of(const Json& r) {
    if (!r.is_object()) {
        return std::nullopt;
    }
    if (r.contains("error")) {
        const Json& e = r["error"];
        if (e.is_object() && e.value("code", Json()).is_string() && e.value("msg", Json()).is_string()) {
            return std::optional<Json>(std::in_place, r);
        }
        return std::nullopt;
    }
    if (!r.value("message", Json()).is_object()) {
        return std::nullopt;
    }
    return std::optional<Json>(std::in_place, r);
}

std::optional<Json> read_reply(const std::string& path) {
    std::optional<Json> r = aos::read_json(path);
    if (!r) {
        return std::nullopt;
    }
    return reply_of(*r);
}

}  // namespace aos::llm_kernel
