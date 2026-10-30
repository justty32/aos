// letter.cpp：【letter】信箱的路徑、信號、寄信的人還在不在（sender.flock）、priority、回信（說明見 aos/llm_kernel.hpp）。
#include "aos/llm_kernel.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <chrono>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <ctime>

#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>

namespace aos::llm_kernel {

std::string Mailbox::tmp() const { return aos::join(root, "tmp"); }
std::string Mailbox::fresh() const { return aos::join(root, "new"); }
std::string Mailbox::cur() const { return aos::join(root, "cur"); }
std::string Mailbox::done() const { return aos::join(root, "done"); }

std::string letter_id() {
    long long ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                       std::chrono::system_clock::now().time_since_epoch()).count();
    std::optional<long long> ticks = aos::proc_started_at_ticks(0);
    char buf[96];
    std::snprintf(buf, sizeof buf, "%020lld.%ld.%lld", ns, (long)getpid(), ticks ? *ticks : -1LL);
    return buf;
}

int hold_sender(const std::string& letter_dir) {
    std::string path = aos::join(letter_dir, SENDER_FLOCK);
    int fd = open(path.c_str(), O_RDWR | O_CREAT | O_CLOEXEC, 0666);
    if (fd < 0) {
        throw Error{code::WriteFailed, "開不了 " + path + "：" + std::strerror(errno)};
    }
    if (flock(fd, LOCK_EX) != 0) {
        int e = errno;
        close(fd);
        throw Error{code::WriteFailed, "鎖不了 " + path + "：" + std::strerror(e)};
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
        throw Error{code::PriorityBad, "level 只收 \"low\"、\"normal\"、\"high\" 或數字，不是 " + aos::dumps(v)};
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
    throw Error{code::PriorityBad, "level 只收 \"low\"、\"normal\"、\"high\" 或數字，不是 " + aos::dumps(v)};
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
    throw Error{code::PriorityBad, "deadline 要是帶時區的 ISO 8601（例 2026-10-24T18:00:00+08:00）或 epoch 秒，不是 " + aos::dumps(v)};
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
    throw Error{code::PriorityBad, "priority 要是 \"low\"／\"normal\"／\"high\"、數字或 {\"level\", \"deadline\"}，不是 " + aos::dumps(v)};
}

// `_metainfo` 的數量類 key：數字＝典型值；物件取 val（C-55 值的雙形）。非負有限數才算，其他＝寫壞。
static std::optional<double> amount(const Json& v) {
    Json x = v;
    if (v.is_object()) {
        x = v.value("val", Json());
    }
    if (x.is_number() && !x.is_boolean()) {
        double d = x.get<double>();
        if (std::isfinite(d) && d >= 0) {
            return d;
        }
    }
    return std::nullopt;
}

Priority priority_of(const Json& letter) {
    Priority p = parse_priority(letter.value("priority", Json()));
    Json inst = letter.value("inst", Json());
    if (!inst.is_object() || !inst.contains("_metainfo")) {
        return p;
    }
    const Json& m = inst["_metainfo"];
    if (!m.is_object()) {
        p.metainfo_bad.push_back("_metainfo");
        return p;
    }
    if (m.contains("time_ms")) {
        p.time_ms = amount(m["time_ms"]);
        if (!p.time_ms) {
            p.metainfo_bad.push_back("time_ms");
        }
    }
    if (m.contains("llm_tokens")) {
        p.llm_tokens = amount(m["llm_tokens"]);
        if (!p.llm_tokens) {
            p.metainfo_bad.push_back("llm_tokens");
        }
    }
    return p;
}

std::string level_name(int level) {
    if (level < 0) {
        return "low";
    }
    if (level > 0) {
        return "high";
    }
    return "normal";
}

std::optional<Json> read_reply(const std::string& path) {
    std::optional<Json> r = aos::read_json(path);
    if (!r || !r->is_object()) {
        return std::nullopt;
    }
    if (r->contains("error")) {
        const Json& e = (*r)["error"];
        if (e.is_object() && e.value("code", Json()).is_string() && e.value("msg", Json()).is_string()) {
            return r;
        }
        return std::nullopt;
    }
    Json c = r->value("code", Json());
    Json s = r->value("signal", Json());
    if (!c.is_number_integer() || !(s.is_null() || s.is_number_integer())) {
        return std::nullopt;
    }
    return r;
}

}  // namespace aos::llm_kernel
