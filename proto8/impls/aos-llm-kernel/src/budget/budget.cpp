// budget.cpp：【budget】token 回報與額度（說明見 budget.hpp）。
#include "budget/budget.hpp"

#include "aos/util/files.hpp"
#include "aos/util/io.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>

namespace fs = std::filesystem;

namespace aos::llm_kernel {

// 一格上限 {"max_calls", "max_tokens"}（寄件人那格；at＝訊息裡的位置）。window／spent 跟 kernel 的同一個，寫了＝CfgBad。
static Limit parse_limit(const Json& v, const std::string& at) {
    Limit l;
    if (!v.is_object()) {
        throw Error{code::CfgBad, at + " must be {\"max_calls\", \"max_tokens\"}, got " + aos::dumps(v)};
    }
    for (auto& [k, x] : v.items()) {
        if (k != "max_calls" && k != "max_tokens") {
            throw Error{code::CfgBad, at + "." + k + " is not allowed (only max_calls, max_tokens; the window and spent are the kernel's budget.window, budget.spent)"};
        }
        if (x.is_null()) {
            continue;
        }
        if (!aos::is_count(x)) {
            throw Error{code::CfgBad, at + "." + k + " must be a non-negative integer (limit per window), got " + aos::dumps(x)};
        }
        (k == "max_calls" ? l.max_calls : l.max_tokens) = x.get<long long>();
    }
    return l;
}

std::string sender_key(const std::string& sender, const std::string& stack) {
    if (sender.empty()) {
        return "";
    }
    fs::path who = fs::path(aos::abspath(sender)).lexically_normal();
    fs::path root = fs::path(aos::abspath(stack)).lexically_normal();
    return who.lexically_relative(root).generic_string();
}

Budget parse_budget(const Json& v, const std::string& base, const std::string& stack) {
    Budget b;
    if (v.is_null()) {
        return b;
    }
    if (!v.is_object()) {
        throw Error{code::CfgBad, "budget must be {\"max_calls\", \"max_tokens\", \"window\", \"spent\"}, got " + aos::dumps(v)};
    }
    for (const char* k : {"max_calls", "max_tokens"}) {
        Json x = v.value(k, Json());
        if (x.is_null()) {
            continue;
        }
        if (!aos::is_count(x)) {
            throw Error{code::CfgBad, std::string("budget.") + k + " must be a non-negative integer (limit per window), got " + aos::dumps(x)};
        }
        (std::string(k) == "max_calls" ? b.max_calls : b.max_tokens) = x.get<long long>();
    }
    Json w = v.value("window", Json());
    if (!w.is_null()) {
        if (!w.is_string() || (w != "hour" && w != "day" && w != "all")) {
            throw Error{code::CfgBad, "budget.window must be \"hour\", \"day\" or \"all\", got " + aos::dumps(w)};
        }
        b.window = w.get<std::string>();
    }
    Json s = v.value("spent", Json());
    if (!s.is_null()) {
        if (!s.is_string() || (s != "refuse" && s != "wait")) {
            throw Error{code::CfgBad, "budget.spent must be \"refuse\" or \"wait\", got " + aos::dumps(s)};
        }
        b.wait = s == "wait";
    }
    Json se = v.value("senders", Json());
    if (!se.is_null()) {
        if (!se.is_object()) {
            throw Error{code::CfgBad, "budget.senders must be {sender: {\"max_calls\", \"max_tokens\"}} (sender = the letter's envelope sender, a path), got " + aos::dumps(se)};
        }
        for (auto& [k, x] : se.items()) {
            if (k.empty()) {
                throw Error{code::CfgBad, "budget.senders: a sender must be a non-empty path"};
            }
            std::string sender = aos::abspath(aos::join(base, k));
            std::string who = sender_key(sender, stack);   // 相對設定檔解位置，再改成相對 kernel stack 的帳目 key
            if (b.senders.count(who)) {
                throw Error{code::CfgBad, "budget.senders: " + k + " names the same sender (" + sender + ") as another key"};
            }
            b.senders[who] = parse_limit(x, "budget.senders." + k);
        }
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
        u.packs = Json::object();
        u.senders = Json::object();
    }
}

// packs、senders 那格（11-05 feat-proto）：沒有＝{}；要是 {代號或寄件人: {"counter_calls", "counter_tokens"}}。
static bool packs_ok(const Json& p) {
    if (!p.is_object()) {
        return false;
    }
    for (auto& [k, v] : p.items()) {
        if (!v.is_object() || !aos::is_count(v.value("counter_calls", Json())) || !aos::is_count(v.value("counter_tokens", Json()))) {
            return false;
        }
    }
    return true;
}

Used read_used(const std::string& stack, const std::string& window) {
    Used u;
    std::string path = aos::join(stack, "used.json");
    int err = 0;
    std::optional<std::string> text = aos::read_file(path, err);
    if (!text) {
        if (err != ENOENT) {
            throw Error{code::UsedBad, "cannot read " + path + ": " + std::strerror(err)};
        }
        u.window = "";   // 第一次：roll 會填上
    } else {
        std::optional<Json> doc = aos::read_json(path);
        bool ok = doc && doc->is_object() && doc->value("window", Json()).is_string() &&
                  (doc->value("since", Json()).is_string() || doc->value("since", Json()).is_null());
        for (const char* k : {"counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens"}) {
            ok = ok && aos::is_count(doc->value(k, Json()));
        }
        ok = ok && (!doc->contains("packs") || packs_ok((*doc)["packs"]));
        ok = ok && (!doc->contains("senders") || packs_ok((*doc)["senders"]));
        if (!ok) {
            throw Error{code::UsedBad, path + " must be {\"window\", \"since\", \"counter_calls\", \"counter_tokens\", \"counter_all_calls\", \"counter_all_tokens\", \"packs\"?: {name: {\"counter_calls\", \"counter_tokens\"}}, \"senders\"?: {sender: {\"counter_calls\", \"counter_tokens\"}}} (delete it to count from 0)"};
        }
        if (doc->contains("packs")) {
            u.packs = (*doc)["packs"];
        }
        if (doc->contains("senders")) {
            u.senders = (*doc)["senders"];
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

// 一格帳（packs 或 senders 的 name 那格）記上一次。
static void count_in(Json& group, const std::string& name, long long t) {
    Json& p = group[name];
    if (!p.is_object()) {
        p = Json::object();
    }
    p["counter_calls"] = p.value("counter_calls", 0LL) + 1;
    p["counter_tokens"] = p.value("counter_tokens", 0LL) + t;
}

void add_used(const std::string& stack, Used& u, const Report& r, const std::string& endpoint, const std::string& sender) {
    roll(u, u.window);
    long long t = r.tokens.is_number_integer() ? r.tokens.get<long long>() : 0;
    u.calls += 1;
    u.tokens += t;
    u.all_calls += 1;
    u.all_tokens += t;
    if (!endpoint.empty()) {
        count_in(u.packs, endpoint, t);
    }
    if (!sender.empty()) {
        count_in(u.senders, sender_key(sender, stack), t);
    }
    Json doc = Json::object();
    doc["window"] = u.window;
    doc["since"] = u.since;
    doc["counter_calls"] = u.calls;
    doc["counter_tokens"] = u.tokens;
    doc["counter_all_calls"] = u.all_calls;
    doc["counter_all_tokens"] = u.all_tokens;
    doc["packs"] = u.packs;
    doc["senders"] = u.senders;
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

bool spent_pack(const Used& u, const std::string& name, std::optional<long long> max_calls, std::optional<long long> max_tokens,
                long long started) {
    return spent_of(u.packs, name, max_calls, max_tokens, started);
}

bool spent_of(const Json& group, const std::string& name, std::optional<long long> max_calls, std::optional<long long> max_tokens,
              long long started) {
    long long calls = 0;
    long long tokens = 0;
    if (group.contains(name) && group[name].is_object()) {
        calls = group[name].value("counter_calls", 0LL);
        tokens = group[name].value("counter_tokens", 0LL);
    }
    if (max_calls && calls + started >= *max_calls) {
        return true;
    }
    return max_tokens && tokens >= *max_tokens;
}

Report report_of(const Json& reply) {
    Report r;
    if (!reply.is_object() || !reply.contains("usage")) {
        return r;   // 沒回報＝只算次數
    }
    const Json& u = reply["usage"];
    if (!u.is_object()) {
        r.bad = true;
        return r;
    }
    Json total = u.value("total_tokens", Json());
    if (aos::is_count(total)) {
        r.tokens = total;
        return r;
    }
    Json p = u.value("prompt_tokens", Json());
    Json c = u.value("completion_tokens", Json());
    if (total.is_null() && aos::is_count(p) && aos::is_count(c)) {
        r.tokens = p.get<long long>() + c.get<long long>();
        return r;
    }
    r.bad = true;
    return r;
}

}  // namespace aos::llm_kernel
