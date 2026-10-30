// budget.cpp：【budget】token 回報與額度（說明見 budget.hpp）。
#include "budget/budget.hpp"

#include "aos/files.hpp"
#include "aos/io.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace aos::llm_kernel {

Budget parse_budget(const Json& v) {
    Budget b;
    if (v.is_null()) {
        return b;
    }
    if (!v.is_object()) {
        throw Error{code::CfgBad, "budget 要是 {\"max_calls\", \"max_tokens\", \"window\", \"spent\"}，不是 " + aos::dumps(v)};
    }
    for (const char* k : {"calls", "tokens"}) {   // 10-25 前的上限名：不認，免得寫舊名的人以為有上限
        if (v.contains(k)) {
            throw Error{code::CfgBad, std::string("budget.") + k + " 是舊名（10-25 改叫 budget.max_" + k + "）"};
        }
    }
    for (const char* k : {"max_calls", "max_tokens"}) {
        Json x = v.value(k, Json());
        if (x.is_null()) {
            continue;
        }
        if (!aos::is_count(x)) {
            throw Error{code::CfgBad, std::string("budget.") + k + " 要是非負整數（每窗上限），不是 " + aos::dumps(x)};
        }
        (std::string(k) == "max_calls" ? b.max_calls : b.max_tokens) = x.get<long long>();
    }
    Json w = v.value("window", Json());
    if (!w.is_null()) {
        if (!w.is_string() || (w != "hour" && w != "day" && w != "all")) {
            throw Error{code::CfgBad, "budget.window 要是 \"hour\"／\"day\"／\"all\"，不是 " + aos::dumps(w)};
        }
        b.window = w.get<std::string>();
    }
    Json s = v.value("spent", Json());
    if (!s.is_null()) {
        if (!s.is_string() || (s != "refuse" && s != "wait")) {
            throw Error{code::CfgBad, "budget.spent 要是 \"refuse\"／\"wait\"，不是 " + aos::dumps(s)};
        }
        b.wait = s == "wait";
    }
    return b;
}

Json window_since(const std::string& window, std::time_t now) {
    if (window == "all") {
        return nullptr;
    }
    std::tm tm{};
    localtime_r(&now, &tm);
    tm.tm_min = 0;
    tm.tm_sec = 0;
    if (window == "day") {
        tm.tm_hour = 0;
    }
    tm.tm_isdst = -1;
    std::time_t start = std::mktime(&tm);
    std::tm st{};
    localtime_r(&start, &st);
    char buf[40];
    std::strftime(buf, sizeof buf, "%Y-%m-%dT%H:%M:%S", &st);
    long off = st.tm_gmtoff;
    char sign = off < 0 ? '-' : '+';
    off = std::labs(off);
    char tz[48];
    std::snprintf(tz, sizeof tz, "%c%02ld:%02ld", sign, off / 3600, (off % 3600) / 60);
    return std::string(buf) + tz;
}

// 換窗：window 或 since 跟現在不同＝這一窗從 0 起（all_* 照留）。
static void roll(Used& u, const std::string& window) {
    Json since = window_since(window, std::time(nullptr));
    if (u.window != window || u.since != since) {
        u.window = window;
        u.since = since;
        u.calls = 0;
        u.tokens = 0;
    }
}

Used read_used(const std::string& stack, const std::string& window) {
    Used u;
    std::string path = aos::join(stack, "used.json");
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        if (err != ENOENT) {
            throw Error{code::UsedBad, "讀不了 " + path + "：" + std::strerror(err)};
        }
        u.window = "";   // 第一次：roll 會填上
    } else {
        std::optional<Json> doc = aos::read_json(path);
        bool ok = doc && doc->is_object() && doc->value("window", Json()).is_string() &&
                  (doc->value("since", Json()).is_string() || doc->value("since", Json()).is_null());
        for (const char* k : {"counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens"}) {
            ok = ok && aos::is_count(doc->value(k, Json()));
        }
        if (!ok) {
            throw Error{code::UsedBad, path + " 要是 {\"window\", \"since\", \"counter_calls\", \"counter_tokens\", \"counter_all_calls\", \"counter_all_tokens\"}（刪掉它就從 0 算）"};
        }
        u.window = (*doc)["window"].get<std::string>();
        u.since = (*doc)["since"];
        u.calls = (*doc)["counter_calls"].get<long long>();
        u.tokens = (*doc)["counter_tokens"].get<long long>();
        u.all_calls = (*doc)["counter_all_calls"].get<long long>();
        u.all_tokens = (*doc)["counter_all_tokens"].get<long long>();
    }
    roll(u, window);
    return u;
}

void add_used(const std::string& stack, Used& u, const Report& r) {
    roll(u, u.window);
    long long t = r.tokens.is_number_integer() ? r.tokens.get<long long>() : 0;
    u.calls += 1;
    u.tokens += t;
    u.all_calls += 1;
    u.all_tokens += t;
    Json doc = Json::object();
    doc["window"] = u.window;
    doc["since"] = u.since;
    doc["counter_calls"] = u.calls;
    doc["counter_tokens"] = u.tokens;
    doc["counter_all_calls"] = u.all_calls;
    doc["counter_all_tokens"] = u.all_tokens;
    std::optional<std::string> err = aos::write_json(aos::join(stack, "used.json"), doc);
    if (err) {
        throw Error{code::WriteFailed, *err};
    }
}

bool spent(const Budget& b, const Used& u, long long started) {
    if (b.max_calls && u.calls + started >= *b.max_calls) {
        return true;
    }
    return b.max_tokens && u.tokens >= *b.max_tokens;
}

Report read_report(const std::string& path) {
    Report r;
    int err = 0;
    if (!aos::read_file(path, err)) {
        r.bad = err != ENOENT;
        return r;
    }
    std::optional<Json> u = aos::read_json(path);
    if (!u || !u->is_object()) {
        r.bad = true;
        return r;
    }
    Json total = u->value("total_tokens", Json());
    if (aos::is_count(total)) {
        r.tokens = total;
        return r;
    }
    Json p = u->value("prompt_tokens", Json());
    Json c = u->value("completion_tokens", Json());
    if (total.is_null() && aos::is_count(p) && aos::is_count(c)) {
        r.tokens = p.get<long long>() + c.get<long long>();
        return r;
    }
    r.bad = true;
    return r;
}

}  // namespace aos::llm_kernel
