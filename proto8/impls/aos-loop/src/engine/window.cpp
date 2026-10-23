// window.cpp：【engine】ctl／state 兩扇窗（NORMS N-06～N-09、N-17、N-32、N-33）。
//
//   read_ctl      回最後一份好的 ctl（一份都沒讀到過＝{}）。認 paused、stopped（布林）、max、interval_ms、seq（非負整數），
//                 加上子類別的 check_ctl；其他 key 忽略。指示詞先解（resolve_keys；10-23 晚）。讀到壞的（讀不了、不是 JSON 物件、
//                 型別不對、指示詞解不開）整份不採用、
//                 維持上一份好的，原因記 ctl_warning（N-08）；讀到好的清回 null。檔不在＝還沒人寫，維持上一份好的、
//                 不算問題（ctl_warning 不動）
//   write_state   state 一份：kind、phase、runs、max、interval_ms、paused、ctl_seq、ctl_warning（生效中的值，ctl 蓋過設定檔之後）
//                 ＋info()＋code（結束時）＋心跳；沒開 state 窗就不寫
//   beat          心跳：離上一次寫 state 滿 1 秒（或還沒寫過）就再寫一份（一輪裡很久的工作用：daemon 起一大批、收工等子項）
//   write_window  先寫同資料夾的 .名字 再改名（N-05）
//   heartbeat     pid、started_at_ticks、boot_id、at（ISO 8601 UTC 到毫秒）
#include "engine/engine.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <cerrno>
#include <cstdio>
#include <cstring>

#include <unistd.h>

namespace aos::loop {

void write_window(const std::string& path, const Json& doc) {
    std::string dir = aos::dirname(path);
    std::string name = path.substr(path.rfind('/') + 1);
    std::string tmp = aos::join(dir, "." + name);
    std::string text = aos::dumps(doc) + "\n";
    FILE* f = std::fopen(tmp.c_str(), "w");
    if (f == nullptr) {
        throw Error{code::WriteFailed, "寫不了 " + tmp + "：" + std::strerror(errno)};
    }
    bool ok = std::fwrite(text.data(), 1, text.size(), f) == text.size();
    ok = std::fclose(f) == 0 && ok;
    if (!ok || std::rename(tmp.c_str(), path.c_str()) != 0) {
        std::string why = std::strerror(errno);
        std::remove(tmp.c_str());
        throw Error{code::WriteFailed, "寫不了 " + path + "：" + why};
    }
}

Json heartbeat() {
    static Json me;   // 自己的 pid、啟動時間、開機 id 只算一次；fork 出來的分身（daemon 的子 loop）pid 不同就重算
    if (me.is_null() || me["pid"] != (long long)getpid()) {
        me = Json::object();
        me["pid"] = (long long)getpid();
        me["started_at_ticks"] = nullptr;
        std::optional<long long> st = aos::proc_started_at_ticks(0);
        if (st) {
            me["started_at_ticks"] = *st;
        }
        me["boot_id"] = nullptr;
        std::optional<std::string> b = aos::boot_id();
        if (b) {
            me["boot_id"] = *b;
        }
    }
    Json out = me;
    out["at"] = aos::utc_now_ms();
    return out;
}

// 不是 nullopt＝不採用的原因。
static std::optional<std::string> check_base(const Json& doc) {
    if (!doc.is_object()) {
        return "要是 JSON 物件";
    }
    const char* bools[2] = {"paused", "stopped"};
    for (const char* k : bools) {
        if (doc.contains(k) && !doc[k].is_boolean()) {
            return std::string(k) + " 要是 true／false";
        }
    }
    const char* nats[3] = {"max", "interval_ms", "seq"};
    for (const char* k : nats) {
        if (doc.contains(k) && !is_nat(doc[k])) {
            return std::string(k) + " 要是非負整數";
        }
    }
    return std::nullopt;
}

Json Loop::read_ctl() {
    if (ctl_path_.empty()) {
        return ctl_good_;
    }
    int err = 0;
    std::optional<std::string> text = aos::read_file(ctl_path_, err);
    if (!text) {
        if (err != ENOENT) {
            ctl_warning_ = std::string("ctl 讀不了或不是 JSON：") + std::strerror(err);
        }
        return ctl_good_;
    }
    Json doc = Json::parse(*text, nullptr, false);
    if (doc.is_discarded()) {
        ctl_warning_ = "ctl 讀不了或不是 JSON：" + ctl_path_;
        return ctl_good_;
    }
    std::optional<std::string> bad;
    try {   // 指示詞（10-23 晚）：相對 $ref 從 ctl 所在的資料夾算；解不開＝整份不採用（N-08）
        aos::Resolved r = resolve_keys(doc, aos::dirname(ctl_path_), {"paused", "stopped", "max", "interval_ms", "seq"});
        doc = std::move(r.value);
        bad = check_base(doc);
        if (!bad) {
            bad = check_ctl(doc, r);
        }
    } catch (const Error& e) {
        bad = "指示詞解不開：" + e.msg;
    }
    if (bad) {
        ctl_warning_ = "ctl 不採用：" + *bad;
        return ctl_good_;
    }
    ctl_good_ = doc;
    ctl_warning_ = nullptr;
    return ctl_good_;
}

void Loop::write_state(const std::string& phase, const Json& code) {
    if (state_path_.empty()) {
        return;
    }
    const Json& c = ctl_now_;
    Json doc = Json::object();
    doc["kind"] = "state";
    doc["phase"] = phase;
    doc["runs"] = runs_;
    if (c.contains("max")) {
        doc["max"] = c["max"];
    } else if (max_) {
        doc["max"] = *max_;
    } else {
        doc["max"] = nullptr;
    }
    doc["interval_ms"] = c.contains("interval_ms") ? c["interval_ms"] : Json(interval_ms_);
    doc["paused"] = c.contains("paused") ? c["paused"] : Json(false);
    doc["ctl_seq"] = c.contains("seq") ? c["seq"] : Json();
    doc["ctl_warning"] = ctl_warning_;
    Json more = info();
    for (auto& [k, v] : more.items()) {
        doc[k] = v;
    }
    if (!code.is_null()) {
        doc["code"] = code;
    }
    Json hb = heartbeat();
    for (auto& [k, v] : hb.items()) {
        doc[k] = v;
    }
    phase_ = phase;
    wrote_ = true;
    wrote_at_ = std::chrono::steady_clock::now();
    try {
        write_window(state_path_, doc);
    } catch (const Error& e) {
        throw StateError{e};
    }
}

void Loop::beat(const std::string& phase) {
    if (state_path_.empty() || (wrote_ && std::chrono::steady_clock::now() - wrote_at_ < std::chrono::seconds(1))) {
        return;
    }
    write_state(phase.empty() ? phase_ : phase, Json());
}

}  // namespace aos::loop
