// window.cpp：【engine】ctl／state 兩扇窗（NORMS N-06～N-09、N-17、N-32、N-33）。
//
//   read_ctl      ctl＝一道指令（11-03，thinking 2026-11-03-ctl-commands）：認 cmd（"pause"／"resume"／"stop"）、max、interval_ms（非負整數或 null）、
//                 seq（非負整數），加上子類別的 check_ctl；其他 key 忽略。指示詞先解（resolve_keys；10-23 晚）。
//                 新舊比內容：這次讀到的跟上一次讀到的一樣＝同一道、不再做；不一樣才照做一次（pause／resume 改 paused_、stop 設 stopping_、
//                 max／interval_ms 寫了才改、null 回設定檔的值；ctl_seq 回音這道的 seq）。起來第一次讀到的＝基準線、不執行（殘留的 stop 不會讓新起的退）。
//                 讀到新的壞的（讀不了、不是 JSON 物件、型別不對、cmd 不認得、指示詞解不開）整份不採用、維持原狀，原因記 ctl_warning（N-08）；
//                 照做了一道好的清回 null（check_ctl 填了 ctl_note_＝那一句）。檔不在＝沒有新指令、維持原狀（之後再寫的一律算新的）。讀的人不刪不改 ctl
//                 新的好壞指令處理完都算有反應（responded）；起來第一次的基準線、檔不在不算
//   read_old_paused  起來時：開了 state 窗、舊的 state.json 是物件而且 paused 是 true＝起來先暫停（11-03 代定，使用者四態「繼續暫停」）；其他欄位不接
//   write_state   state 一份：phase、counter_runs（跑過幾次；10-25 原 runs、同日再改 counter_runs）、max、interval_ms、paused、ctl_seq、ctl_warning（生效中的值，ctl 的指令改過之後）
//                 ＋info()＋code（結束時）＋proc_fields＋responded_at＋updated_at（updated_at 最後一欄）；responded_at 算進變動比較，沒開 state 窗就不寫；
//                 有變才寫（11-02）：組好的這份（不含 updated_at、counter_runs；running／waiting 互換當沒變，11-02 晚）跟上一份寫出去的一樣就不碰檔；第一份、帶 code 的一定寫；
//                 接著呼叫 write_more（子類別的窗，自己比有沒有變；10-29）。11-02 拿掉 beat（每秒的心跳）
//   log_line      stdout 一行 JSON（11-02；11-02 晚起 --enable-logs 才印）：一次 write；寫的那一下擋 SIGPIPE、排著的吃掉、還原遮罩；印不了＝之後不印、不退出
//   write_window  先寫同資料夾的 .名字 再改名（N-05）
//   proc_fields   pid、started_at_ticks、boot_id（11-02 原 heartbeat，時間欄拿掉）
#include "engine/engine.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <ctime>

#include <pthread.h>
#include <signal.h>
#include <unistd.h>

namespace aos::loop {

void write_window(const std::string& path, const Json& doc) {
    std::string dir = aos::dirname(path);
    std::string name = path.substr(path.rfind('/') + 1);
    std::string tmp = aos::join(dir, "." + name);
    std::string text = aos::dumps(doc) + "\n";
    FILE* f = std::fopen(tmp.c_str(), "w");
    if (f == nullptr) {
        throw Error{code::WriteFailed, "cannot write " + tmp + ": " + std::strerror(errno)};
    }
    bool ok = std::fwrite(text.data(), 1, text.size(), f) == text.size();
    ok = std::fclose(f) == 0 && ok;
    if (!ok || std::rename(tmp.c_str(), path.c_str()) != 0) {
        std::string why = std::strerror(errno);
        std::remove(tmp.c_str());
        throw Error{code::WriteFailed, "cannot write " + path + ": " + why};
    }
}

Json proc_fields() {
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
    return me;
}

void Loop::log_line(const Json& doc) {
    if (!log_) {
        return;
    }
    std::string text = aos::dumps(doc) + "\n";
    // stdout 是關掉的管子時 write 會發 SIGPIPE、預設處置把這支程式打死。不改處置（SIG_IGN 會被 exec 的子行程繼承、改了身體的行為），
    // 只在這一下擋著：寫完（EPIPE）排著的 SIGPIPE 用零逾時的 sigtimedwait 吃掉，再還原遮罩。子行程 fork 時遮罩已還原，不受影響。
    sigset_t pipe_set;
    sigset_t old;
    sigemptyset(&pipe_set);
    sigaddset(&pipe_set, SIGPIPE);
    pthread_sigmask(SIG_BLOCK, &pipe_set, &old);
    bool ok = true;
    size_t off = 0;
    while (off < text.size()) {
        ssize_t n = ::write(STDOUT_FILENO, text.data() + off, text.size() - off);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n <= 0) {
            ok = false;
            break;
        }
        off += (size_t)n;
    }
    if (!ok && !sigismember(&old, SIGPIPE)) {
        timespec zero{0, 0};
        while (sigtimedwait(&pipe_set, nullptr, &zero) > 0) {
        }
    }
    pthread_sigmask(SIG_SETMASK, &old, nullptr);
    if (!ok) {
        log_ = false;   // 印不了：之後都不印，照常跑（log 是給人看的，不是這支程式的工作）
    }
}

// 不是 nullopt＝不採用的原因。
static std::optional<std::string> check_base(const Json& doc) {
    if (!doc.is_object()) {
        return "must be a JSON object";
    }
    if (doc.contains("cmd")) {
        const Json& c = doc["cmd"];
        if (!c.is_string() || (c != "pause" && c != "resume" && c != "stop")) {
            return "cmd must be \"pause\", \"resume\" or \"stop\"";
        }
    }
    const char* nats[2] = {"max", "interval_ms"};   // null＝回設定檔的值（11-03）
    for (const char* k : nats) {
        if (doc.contains(k) && !doc[k].is_null() && !is_nat(doc[k])) {
            return std::string(k) + " must be a non-negative integer or null";
        }
    }
    if (doc.contains("seq") && !is_nat(doc["seq"])) {
        return "seq must be a non-negative integer";
    }
    return std::nullopt;
}

void Loop::read_ctl() {
    if (ctl_path_.empty()) {
        return;
    }
    // 新舊比內容（11-03）：seen＝這次讀到的（好的＝解完那份的字串；壞的＝"!"＋原文；檔不在＝空）。
    // 第一次讀＝基準線：記下來、不執行、不提醒。
    bool first = !ctl_seen_;
    ctl_seen_ = true;
    int err = 0;
    std::optional<std::string> text = aos::read_file(ctl_path_, err);
    if (!text) {
        std::string seen = err == ENOENT ? std::string() : "!" + std::to_string(err);
        bool fresh = seen != ctl_last_;
        ctl_last_ = seen;
        if (!first && fresh && err != ENOENT) {
            ctl_warning_ = std::string("ctl: cannot read or not JSON: ") + std::strerror(err);
            responded();
        }
        return;   // 檔不在＝沒有新指令（之後再寫的都算新的）
    }
    Json doc = Json::parse(*text, nullptr, false);
    std::optional<std::string> bad;
    std::string seen = "!" + *text;
    if (doc.is_discarded()) {
        bad = "cannot read or not JSON: " + ctl_path_;
    } else {
        try {   // 指示詞（10-23 晚）：相對 $ref 從 ctl 所在的資料夾算；解不開＝整份不採用（N-08）
            aos::Resolved r = resolve_keys(doc, aos::dirname(ctl_path_), {"cmd", "max", "interval_ms", "seq"});
            doc = std::move(r.value);
            bad = check_base(doc);
            if (!bad) {
                ctl_note_.clear();
                bad = check_ctl(doc, r);
            }
        } catch (const Error& e) {
            bad = "cannot resolve directives: " + e.msg;
        }
        if (!bad) {
            seen = aos::dumps(doc);
        }
    }
    if (seen == ctl_last_) {
        return;   // 同一道（或同一份壞的）：不再做
    }
    ctl_last_ = seen;
    if (first) {
        return;   // 基準線：起來前就在的那份當已經看過
    }
    if (bad) {
        ctl_warning_ = (doc.is_discarded() ? "ctl: " : "ctl rejected: ") + *bad;
        responded();
        return;
    }
    // 照做一次。stop 壓過同一道裡的其他東西（N-07 stopped 壓過 paused，11-03 照舊）
    std::string cmd = doc.contains("cmd") ? doc["cmd"].get<std::string>() : "";
    if (cmd == "stop") {
        stopping_ = true;
    } else if (cmd == "pause") {
        paused_ = true;
    } else if (cmd == "resume") {
        paused_ = false;
    }
    if (doc.contains("max")) {
        max_ = doc["max"].is_null() ? max_base_ : std::optional<long long>(doc["max"].get<long long>());
    }
    if (doc.contains("interval_ms")) {
        interval_ms_ = doc["interval_ms"].is_null() ? interval_base_ : doc["interval_ms"].get<long long>();
    }
    ctl_seq_ = doc.contains("seq") ? doc["seq"] : Json();
    ctl_warning_ = ctl_note_.empty() ? Json() : Json(ctl_note_);   // 照做了但子類別要提醒的（10-29 daemon 過渡期）
    responded();
}

void Loop::read_old_paused() {
    if (state_path_.empty()) {
        return;
    }
    int err = 0;
    std::optional<std::string> text = aos::read_file(state_path_, err);
    if (!text) {
        return;
    }
    Json old = Json::parse(*text, nullptr, false);
    if (old.is_object() && old.contains("paused") && old["paused"] == true) {
        paused_ = true;
    }
}

void Loop::write_state(const std::string& phase, const Json& code) {
    Json me = proc_fields();
    if (!state_path_.empty()) {
        write_main(phase, code, me);
    }
    try {   // 子類別自己的狀態窗（10-29 daemon 的 loops_state）：有沒有變它自己比（11-02）
        write_more(me);
    } catch (const StateError&) {
        throw;
    } catch (const Error& e) {
        throw StateError{e};
    }
}

void Loop::write_main(const std::string& phase, const Json& code, const Json& me) {
    Json doc = Json::object();
    doc["phase"] = phase;
    doc["counter_runs"] = runs_;
    doc["max"] = max_ ? Json(*max_) : Json();
    doc["interval_ms"] = interval_ms_;
    doc["paused"] = paused_;
    doc["ctl_seq"] = ctl_seq_;
    doc["ctl_warning"] = ctl_warning_;
    Json more = info();
    for (auto& [k, v] : more.items()) {
        doc[k] = v;
    }
    if (!code.is_null()) {
        doc["code"] = code;
    }
    for (auto& [k, v] : me.items()) {
        doc[k] = v;
    }
    doc["responded_at"] = responded_at_;
    // 有變才寫（11-02）：counter_runs 不算變動（使用者「對」）——比的時候拿掉，寫出去照帶當下的快照
    Json key = doc;
    key.erase("counter_runs");
    if (phase == "running" || phase == "waiting") {
        key["phase"] = "running|waiting";   // 11-02 晚：running ⇄ waiting 不算變動（只比進出 paused／stopping／stopped／done）
    }
    if (wrote_ && code.is_null() && key == last_main_) {
        return;
    }
    doc["updated_at"] = aos::utc_now_ms();
    try {
        write_window(state_path_, doc);
    } catch (const Error& e) {
        throw StateError{e};
    }
    wrote_ = true;
    last_main_ = std::move(key);
}

}  // namespace aos::loop
