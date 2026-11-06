// table.cpp：【daemon】維護 proc 表、記錄子項與處理狀態窗寫入結果（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"

namespace aos::daemon {

void Daemon::add(const std::string& name, const Child& c) {
    table_.push_back({name, c});
    index_[name] = std::prev(table_.end());
    if (!c.held) {
        log_child(name, c);   // 起來（或 adopt 接回）一行；stopped 的列沒有行程，不印
    }
    responded();
}

void Daemon::log_child(const std::string& name, const Child& c) {
    Json line = Json::object();
    line["at"] = aos::utc_now_ms();
    line["name"] = name;
    line["phase"] = c.phase;
    line["pid"] = (long long)c.pid;
    line["code"] = c.code;
    line["signal"] = c.signal;
    if (!c.ws.is_null()) {
        line["ws"] = c.ws;
    }
    log_line(line);
}

Daemon::Table::iterator Daemon::drop(Table::iterator it) {
    auto& [n, c] = *it;
    if (!c.held) {
        log_child(n, c);   // 結束一行（done／stopped，帶 code、signal）；stopped 的列被 rm 沒有行程結束，不印
    }
    if (c.phase == "done") {   // 自己結束的：本次執行不再起（11-02）。開了信箱再從底拿掉（之後再有信同名 procs_added＝重新起）
        if (!mbox_path_.empty()) {
            want_.erase(n);
        }
        ended_.insert(n);
    }
    stopped_.erase(n);   // 表上沒有了＝對 daemon 不存在：底的 stopped／slept 集合也不留它
    slept_.erase(n);
    index_.erase(n);
    responded();
    return table_.erase(it);   // 小格（stack）留著
}

void Daemon::flush_table() {
    try {
        write_more(aos::loop::proc_fields());
    } catch (const Error& e) {
        state_failed(e);
    }
}

// 11-05（edge-round2 題 1，使用者「記一行、下一圈再試 (Recommended)」）：state.json／procs_state.json 寫不了（磁碟滿、stack 被改唯讀）＝不收工，
// 跟身體失敗一樣 stderr 一行（原因變了才印；好了印一行 written again）、proc 照顧著；下一圈再寫——兩扇窗都是「有變才寫」、比的是上一份寫成的，
// 寫不了的那份沒記成「寫過」，下一次 write_state／flush_table 自然重寫。P-36「寫好狀態再結束」的例外：收工那份寫不了也照常結束（碼照舊）。
// 起來之後一份都還沒寫成（stack 不在、一起來就寫不了）＝照舊丟 StateError、退 1（設定或環境錯，當場看得到）。
void Daemon::write_state(const std::string& phase, const Json& code) {
    try {
        Loop::write_state(phase, code);
    } catch (const Error& e) {
        state_failed(e);
        return;
    }
    state_ok();
}

void Daemon::state_failed(const Error& e) {
    if (!state_wrote_) {
        throw aos::loop::StateError{e};
    }
    // 只比代號（state.json、procs_state.json 輪流寫不了時訊息裡的檔名不同，比整句會每圈印）
    if (e.code != state_bad_) {
        warn("cannot write the state windows (" + e.code + " " + e.msg + "), retrying next round");
        state_bad_ = e.code;
    }
}

void Daemon::state_ok() {
    state_wrote_ = true;
    if (!state_bad_.empty()) {
        warn("state windows written again");
        state_bad_.clear();
    }
}

Json Daemon::info() {
    Json o = Json::object();
    o["daemon"] = parent_;
    if (has_body_) {
        o["body_code"] = body_code_;   // 11-05：身體最後一次的結束碼（null＝還沒跑過）
    }
    return o;
}


}  // namespace aos::daemon
