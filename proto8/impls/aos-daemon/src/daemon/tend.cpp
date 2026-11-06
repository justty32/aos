// tend.cpp：【daemon】停止、收回與照顧子項，並在 daemon 收工時等它們退完（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"
#include <csignal>
#include <filesystem>
#include <sstream>
#include <thread>
#include <unordered_map>
#include <unistd.h>

namespace aos::daemon {

using aos::loop::CtlWindow;

using Clock = std::chrono::steady_clock;

static const int GRACE_MS = 10000;   // 收子項：SIGTERM 後等幾毫秒才 SIGKILL（P-36 daemon 的 grace 慣例 10000）
// root 底下（子、孫…）自己當群組組長的行程：/proc 掃一遍（stat 第 4 欄 ppid、第 5 欄 pgrp）。SIGKILL 子 loop 時一起整群收（10-24 審後補）：
// 子 loop 跑的單子——內嵌的在子 loop 自己行程內 run_inst、字串目標的在它 fork 的 aos-exec 裡——由 aos-inst 起、自成 session，
// 整群打子 loop 打不到；單子不理 SIGTERM、grace_ms 又比 10 秒長時，子 loop 被收掉後它會留成孤兒。掃完到送之間它結束了、
// pid 又剛好被別的組長拿走的機會跟 killpg 本身一樣小，不管。讀不到 /proc＝回空的（只收子 loop 那群，同以前）。
static std::vector<pid_t> leaders_below(pid_t root) {
    std::unordered_map<pid_t, std::vector<pid_t>> kids;
    std::unordered_map<pid_t, pid_t> pgrp;
    std::error_code ec;
    for (std::filesystem::directory_iterator it("/proc", ec), end; !ec && it != end; it.increment(ec)) {
        std::string n = it->path().filename().string();
        if (n.empty() || n.find_first_not_of("0123456789") != std::string::npos) {
            continue;
        }
        int err = 0;
        std::optional<std::string> text = aos::read_file("/proc/" + n + "/stat", err);
        size_t paren = text ? text->rfind(')') : std::string::npos;
        if (paren == std::string::npos) {
            continue;
        }
        std::istringstream rest(text->substr(paren + 1));   // 第 2 欄程式名可能有空白：從最後一個 ')' 之後數
        std::string state;
        long ppid = 0;
        long pg = 0;
        if (!(rest >> state >> ppid >> pg)) {
            continue;
        }
        pid_t pid = (pid_t)std::stol(n);
        kids[(pid_t)ppid].push_back(pid);
        pgrp[pid] = (pid_t)pg;
    }
    std::vector<pid_t> out;
    std::vector<pid_t> todo{root};
    while (!todo.empty()) {
        pid_t p = todo.back();
        todo.pop_back();
        for (pid_t k : kids[p]) {
            if (pgrp[k] == k) {
                out.push_back(k);
            }
            todo.push_back(k);
        }
    }
    return out;
}

void Daemon::term(Child& c) {
    c.stuck = false;
    c.stuck_deadline.reset();
    c.phase = "stopping";
    c.termed = true;
    c.deadline = Clock::now() + std::chrono::milliseconds(GRACE_MS);
    kill(c.pid, SIGTERM);   // 給那支子項（它自己轉給它的那次）；已經沒了就算了
}

void Daemon::halt(const std::string& name, Child& c) {
    // daemon 的 stop（procs § 2c 第 2 條、ctl-commands § 5）：往子 loop 的 ctl.json 寫一道 {"cmd": "stop", "seq": N}，讓它跑完這次自己退 0（不 SIGTERM）。
    // ctl 檔名看小格裡 daemon 自己寫的 loop.json（procs_loop 的名字）的 ctl（接回的也一樣）；N＝自己數的、也比 ctl 裡現有的 seq 大（內容一定跟上一道不一樣）。
    // ctl 沒寫＝ctl.json（aos-loop 的預設名，11-04 起 daemon 不再替它補）；讀不到 loop.json、ctl 不是檔名（寫了 null＝子 loop 沒開 ctl）＝改送 SIGTERM（同樣退了就留成 stopped）
    c.soft = true;
    std::optional<Json> cfg = aos::read_json(aos::join(c.stack, names_.loop));
    Json ctl;
    if (cfg && cfg->is_object()) {
        ctl = cfg->value(CtlWindow::config_key, Json(CtlWindow::default_name));
    }
    if (!ctl.is_string() || ctl.get<std::string>().empty()) {
        term(c);
        return;
    }
    std::string path = aos::join(c.stack, ctl.get<std::string>());
    std::optional<Json> old = aos::read_json(path);
    Json old_seq = old && old->is_object() ? old->value(CtlWindow::seq, Json()) : Json();
    if (aos::is_count(old_seq) && old_seq.get<long long>() > stop_seq_) {
        stop_seq_ = old_seq.get<long long>();
    }
    stop_seq_ += 1;
    try {
        aos::loop::write_window(path, Json::object({{CtlWindow::cmd, CtlWindow::stop}, {CtlWindow::seq, stop_seq_}}));
    } catch (const Error& e) {
        // 11-05 第二輪：原本整台 daemon 退 1（一個小格唯讀就把全部 proc 收掉）；改成這一支改送 SIGTERM（同沒開 ctl 的），退了照樣留 stopped
        warn("cannot stop " + name + " through its ctl (" + e.code + " " + e.msg + "); sending SIGTERM instead");
        term(c);
        return;
    }
    c.phase = "stopping";
}

void Daemon::hold(const std::string& name, Child& c, const char* phase, const char* log_phase) {
    c.stuck = false;
    c.stuck_deadline.reset();
    c.phase = log_phase ? log_phase : phase;   // auto_restart 自己退的 log 記 done，表留 sleeping
    log_child(name, c);   // 行程結束一行
    c.phase = phase;
    c.held = true;        // 列留在表上（procs § 2c 第 2 條）：pid null、stack 不碰
    c.soft = false;
    c.nap = false;
    c.termed = false;
    c.killed = false;
    c.pid = 0;
    c.started_at_ticks.reset();
    responded();
}

bool Daemon::settle(Child& c) {
    if (!alive(c)) {
        c.phase = "stopped";   // 行程不在了
        return true;
    }
    if (c.termed && !c.killed && Clock::now() >= c.deadline) {   // 寫 ctl 的 stop 沒有時間上限，只有送過 SIGTERM 的才 SIGKILL
        std::vector<pid_t> below = leaders_below(c.pid);   // 先掃：子 loop 一死，底下自成 session 的單子就認不出是誰的了
        aos::signal_group(c.pid, SIGKILL);   // 整群：子 loop 與它同群的孫程式
        for (pid_t g : below) {
            aos::signal_group(g, SIGKILL);   // 底下自成一群的（inst 起的單子，連它的子孫）
        }
        c.killed = true;
    }
    return false;
}


// 不調表地看一眼：stopped／sleeping 的列不動；running 的退了＝done（stop＝daemon 正要停它＝留成 stopped 的列；loop 型出錯結束＝留成 stopped＋reason，11-05）；收的途中的照收，
// 退了：daemon 下的 stop（soft）＝留成 stopped 的列、收工時收的 loop 型（nap）＝留成 sleeping 的列，其他（被收掉的）＝拿掉。回 true＝這列結束了、要拿掉。
bool Daemon::look(const std::string& name, Child& c, bool stop, bool watch) {
    if (c.held) {
        return false;
    }
    if (c.phase == "running") {
        if (alive(c)) {
            if (watch) {
                check_stuck(name, c);
            }
            return false;
        }
        if (stop) {
            hold(name, c);
            return false;
        }
        if (c.auto_restart) {   // 11-06（no-pid P6）：不論型別與結束碼（含接回拿不到碼），照表重起
            bool quick = c.revived && Clock::now() - c.revived_at < std::chrono::milliseconds(REVIVE_MS);
            c.quick_exits = quick ? c.quick_exits + 1 : 0;
            if (c.quick_exits >= 3) {
                c.reason = fail_reason(c) + "; restarted 3 times in a row, each exited within 3s; not restarting again";
                hold(name, c);
                c.failed = true;
                stopped_.insert(name);
            } else {
                hold(name, c, "sleeping", "done");
            }
            return false;
        }
        // 11-05（edge-agent 題 1「留表標 stopped (Recommended)」、edge-daemon 題 2「一起改成留表 (Recommended)」）：
        // loop 型出錯結束（結束碼非 0，含被訊號打掉的 128＋N）＝不下表，留成 stopped（要 start 才再起）＋reason（見 fail_reason）。
        // 3 秒（REVIVE_MS）只分原因字樣（起不來／跑到一半掛了）。退 0（做完：跑滿、身體退 10、別人往它的 ctl 寫 stop）照舊下表；
        // exec 型（只有跑和拔，start 不收它）、接回來的（不是自己生的、拿不到結束碼）也照舊下表。
        if (!c.once && c.code.is_number_integer() && c.code.get<long long>() != 0) {
            c.reason = fail_reason(c);
            hold(name, c);
            c.failed = true;   // 這一圈的起少的不再起它（stopped 參數是這圈開頭算的）
            stopped_.insert(name);
            return false;
        }
        c.phase = "done";   // 自己結束：照 11-02 從表上拿掉
        return true;
    }
    if (c.phase == "stopping" && settle(c)) {
        if (c.stuck_restart) {
            c.stuck_restart = false;
            c.stuck = false;
            c.stuck_deadline.reset();
            if (c.stuck_restarts >= 3) {
                c.reason = "became stuck 3 times in a row without a response; not restarting again";
                hold(name, c);
                c.failed = true;
                stopped_.insert(name);
            } else {
                hold(name, c, "sleeping");
            }
            return false;
        }
        if (c.soft) {
            hold(name, c);
            return false;
        }
        if (c.nap) {
            hold(name, c, "sleeping");
            return false;
        }
        return true;
    }
    return false;
}

void Daemon::tend() {
    read_procs_ctl();   // 每圈先讀 ctl.json（Loop）、再讀 procs_ctl.json；停著、暫停也照讀
    if (stopping_ || paused_) {   // ctl 的 stop／pause（11-03 起是指令，Loop 照做完放在這兩格）
        // 這圈收工／整圈暫停（10-29 medium-plan § 四 2）：不調表、起停也等解除，只看一眼
        for (auto it = table_.begin(); it != table_.end();) {
            if (look(it->first, it->second, false)) {
                it = drop(it);
            } else {
                ++it;
            }
        }
        was_paused_ = paused_;
        return;   // 接著 Loop 寫 paused／stopped 的 state（連 procs_state），不必另寫
    }
    if (was_paused_) {
        // 11-05 第二輪：resume 那一圈先寫一份 state（paused false、新的 ctl_seq）再套信對表。原本對完表才寫：一大批信要好幾秒，
        // 這段時間 state 還寫著暫停；這時 kill -9 再起＝照舊 state「起來先暫停」、ctl 裡那道 resume 又被當基準線＝一直停著
        was_paused_ = false;
        write_state("waiting", Json());
    }
    // 信箱與 procs_ctl 共存——先套信（一次性的改動，改的是底 want_／stopped_），再把 procs_ctl（宣告）疊在底上算期望表
    Letters got;
    if (!mbox_path_.empty()) {
        for (auto it = ended_.begin(); it != ended_.end();) {   // 底來的已經從底拿掉了：放掉，信再加同名就起（procs_ctl 疊的留著）
            if (from_ctl(*it)) {
                ++it;
            } else {
                it = ended_.erase(it);
            }
        }
        got = take_letters();   // 全部認領、照順序套進底，套完才對一次表、再回信收信
    }
    Json merged;
    const Json& want = ctl_want(pctl_good_, merged);   // 沒開 procs_ctl：pctl_good_ 一直是 {}＝期望表就是底
    for (auto it = ended_.begin(); it != ended_.end();) {   // 期望表裡沒有它了＝之後名單再有它就照常起（11-02）
        if (want.contains(*it)) {
            ++it;
        } else {
            it = ended_.erase(it);
        }
    }
    reconcile(want, ctl_stopped(pctl_good_), ctl_slept(pctl_good_));
    if (!mbox_path_.empty()) {
        done_letters(got);
    }
    run_body();   // 11-05：身體在對完表之後跑（同 Loop：tend 之後才跑那次）
}
void Daemon::finish() {
    bool any = false;
    for (auto& [n, c] : table_) {
        if (c.held) {
            continue;   // stopped／sleeping 的列：照寫進最後一份 state（procs § 2c 第 9 條）
        }
        if (c.stuck_restart) {
            c.nap = !c.once || c.auto_restart;   // 卡住重起收途中改為收工，常駐列仍須留 sleeping。
            c.stuck_restart = false;
        }
        if (c.phase == "running" && alive(c)) {
            c.nap = !c.once || c.auto_restart;   // 收工時常駐的退了留 sleeping、再開自動 wake；一般 exec 型拿掉
            term(c);
        } else if (c.phase == "stopping" && !c.termed) {
            term(c);   // 等它自己退的（soft）也改送 SIGTERM；退了照樣留成 stopped 的列
        }
        any = any || c.phase == "stopping";
    }
    if (any) {
        try {
            write_state("stopping", Json());   // 等子項退：state 寫一份 stopping（連 procs_state）；寫不了就算了，收子項要緊
        } catch (const Error&) {
        }
    }
    while (true) {   // 結束的印 log、拿掉，每退一批寫一次 procs_state
        bool waiting = false;
        bool changed = false;
        for (auto it = table_.begin(); it != table_.end();) {
            auto& [n, c] = *it;
            bool was = c.held;
            if (look(n, c, false)) {   // 最後一次 tend 之後才自己結束的（沒送 SIGTERM）標 done、記 code（10-21 plan D7）
                it = drop(it);
                changed = true;
                continue;
            }
            changed = changed || was != c.held;
            waiting = waiting || !c.held;
            ++it;
        }
        if (changed) {
            try {
                flush_table();
            } catch (const Error&) {
            }
        }
        if (!waiting) {
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
}

}  // namespace aos::daemon
