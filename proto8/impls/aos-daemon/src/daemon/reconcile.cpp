// reconcile.cpp：【daemon】按期望表啟動、收回與調整子項（說明見 daemon.hpp）。
#include "daemon/daemon.hpp"
#include "aos/util/files.hpp"
#include <filesystem>
#include <unordered_map>

namespace aos::daemon {

using Clock = std::chrono::steady_clock;

static const int FLUSH_MS = 200;     // 11-05 第二輪：對表起一大批時 procs_state 最多多久寫一次
std::string Daemon::cell_of(const std::string& name, const Json& spec) const {
    if (spec.is_object() && spec.contains("stack")) {
        return spec["stack"].get<std::string>();   // read_procs 已轉絕對（procs § 2b）
    }
    return dstack_ + "procs/" + name;   // 預設小格（11-03 原 loops/<名字>/）
}

Json Daemon::limits_of(const Json& spec, const Json& kept) const {
    Json l = spec.is_null() ? kept : spec.is_object() && spec.contains("limits") ? spec["limits"] : limits_;
    return l.is_object() && !l.empty() ? l : Json();   // {}＝不限（蓋過預設）
}

Child Daemon::start(const std::string& name, const Json& spec, const std::string& cell, const Json& kept_ws, const Json& kept_exec,
                    const Json& kept_def, const Json& kept_limits, const Json& kept_launch, bool kept_auto_restart, bool kept_ros, long long kept_stuck_after_cycles,
                    std::optional<long long> kept_stuck_after_ms) {
    Json lim = limits_of(spec, kept_limits);
    Json launch_spec = spec.is_null() ? kept_launch : spec;
    bool once = is_once(launch_spec);
    bool auto_restart = spec.is_null() ? kept_auto_restart : auto_restart_of(spec);
    bool ros = spec.is_null() ? kept_ros : ros_of(spec);
    long long stuck_cycles = spec.is_null() ? kept_stuck_after_cycles : spec.is_object() ? spec.value("stuck_after_cycles", 10LL) : 10;
    std::optional<long long> stuck_ms;
    if (spec.is_null()) {
        stuck_ms = kept_stuck_after_ms;
    } else if (spec.is_object() && spec.contains("stuck_after_ms")) {
        stuck_ms = spec["stuck_after_ms"].get<long long>();
    }
    bool deep = cell != dstack_ + "procs/" + name;   // 不是預設小格＝proc 自己的 stack：不在就 mkdir -p
    if (auto live = live_in_cell(cell, names_.loop)) {   // 11-05 第二輪：小格裡已有活著的子 loop（上一個 daemon 起了、沒記進表就死）＝接回、不再起一份
        Child c;
        // 起法只在這裡用；接回後保留可重放的入口，不靠小格檔案判身分。
        c.launch = spec.is_null() ? kept_launch : Json::object({{"exec", once ?
            (spec.is_object() && spec["exec"].is_object() ? Json::array({aos::join(cell, names_.exec) + "#/exec"}) :
             spec.is_object() ? spec["exec"] : spec) : Json::array({aos::join(cell, names_.loop) + "#/_entry"})}});
        c.launch = launch_of(c.launch, cwd_);
        c.own = false;
        c.pid = live->first;
        c.started_at_ticks = live->second;
        c.stack = cell;
        c.ws = spec.is_object() && spec.contains("ws") ? spec["ws"] : kept_ws;
        c.exec = spec.is_null() ? kept_exec : exec_of(spec, cwd_);
        c.def = spec.is_null() ? kept_def : def_of(spec);
        c.limits = lim;
        c.auto_restart = auto_restart;
        c.restart_on_stuck = ros;
        c.stuck_after_cycles = stuck_cycles;
        c.stuck_after_ms = stuck_ms;
        std::error_code ec;
        std::uintmax_t sz = std::filesystem::file_size(aos::join(cell, names_.err), ec);
        c.err_off = ec ? 0 : (long long)sz;
        return c;
    }
    Child c;
    try {
        if (launch_spec.is_null()) {
            throw Error{code::LaunchFailed, "no recorded launch entry for " + name};
        }
        if (spec.is_null() && launch_spec.is_object()) {
            launch_spec["ws"] = kept_ws;
        }
        if (once) {
            c = spawn_exec(name, cell, deep, launch_spec, cwd_, dstack_, names_, lim);
        } else {
            c = spawn(name, cell, deep, launch_spec, cwd_, dstack_, names_, lim, kept_ws);
        }
    } catch (const Error& e) {
        // 一列起不來也留 stopped，不讓整台 daemon 收工。
        c.launch = launch_of(launch_spec, cwd_);
        c.stack = cell;
        c.ws = spec.is_object() ? spec.value("ws", Json()) : kept_ws;
        c.limits = lim;
        c.code = 1;
        c.reason = "failed to start: " + e.code + " " + e.msg;
        c.phase = "stopped";
        c.held = true;
        c.failed = true;
        stopped_.insert(name);
        warn("cannot start " + name + " (" + e.code + " " + e.msg + "); leaving it stopped");
    }
    c.exec = spec.is_null() ? kept_exec : exec_of(spec, cwd_);   // 11-04 晚：列上的 exec 欄
    c.def = spec.is_null() ? kept_def : def_of(spec);              // 11-04：列上的 def 欄
    c.auto_restart = auto_restart;
    c.restart_on_stuck = ros;
    c.stuck_after_cycles = stuck_cycles;
    c.stuck_after_ms = stuck_ms;
    return c;
}

void Daemon::reconcile(const Json& want, const Names& stopped, const Names& slept) {
    std::unordered_map<std::string, const Json*> wanted;   // want 是 ordered_json，contains 是逐個比對；先收成雜湊表
    wanted.reserve(want.size());
    for (auto& [n, spec] : want.items()) {
        wanted.emplace(n, &spec);
    }
    for (auto it = table_.begin(); it != table_.end();) {
        auto& [n, c] = *it;
        bool in = wanted.count(n) > 0;
        bool stop = in && stopped.count(n) > 0;
        bool nap = in && !stop && slept.count(n) > 0;   // 11-05 sleep：現在就睡（SIGTERM、10 秒 KILL、列 sleeping），wake 或 daemon 重開才醒
        if (c.stuck_restart && (!in || stop || nap)) {
            c.stuck_restart = false;   // 人工命令優先於卡住重起。
            c.soft = stop;
            c.nap = nap;
        }
        if (look(n, c, stop, in && !stop && !nap)) {
            it = drop(it);   // 已自然退 0 或完成移除：印 log、下表，小格留著
            continue;
        }
        if (c.held) {
            if (!in) {
                it = drop(it);   // stopped／sleeping 的被 rm（或名單上沒有了）：列與集合都拿掉（stack 不碰）
                continue;
            }
            if (stop && c.phase == "sleeping") {
                c.phase = "stopped";   // 睡著的被 stop（例：daemon 沒在跑時寄的 procs_stopped）：不 wake，改成 stopped、要 start 才起
            }
        } else if (c.phase == "running") {
            if (!in) {
                term(c);         // 表上多出來的：送 SIGTERM 就往下走，不等（10-23 壓測後改）
            } else if (stop) {
                halt(n, c);      // daemon 的 stop：寫子 loop 的 ctl，等它跑完這次自己退
            } else if (nap) {
                c.nap = true;    // 11-05 sleep：同收工那套，退了列留成 sleeping
                term(c);
            }
        } else if (c.phase == "stopping" && c.soft && !c.termed && (!in || slept.count(n) > 0)) {
            slept_.erase(n);     // stop 中的 sleep 只升級停止，不留下之後 start 又睡下的意圖
            term(c);             // 等它自己退的途中收到 sleep／rm：改送 SIGTERM；soft 保留，sleep 退後仍 stopped
        }
        ++it;
    }
    flush_table();   // 起之前先寫一份（退掉的、回音待更新的；起一大批要好一陣子），沒變就不寫
    // null＝信箱模式接回的（只留名、沒有設定），只從 held 的列照保留的型別與目標再起；收的途中（stopping）的同名項還在表上：等它退了、下一次才起；
    // 本次執行已自己結束的（ended_）不起
    // 11-05 第二輪：起的途中每 FLUSH_MS 最多寫一次 procs_state（原本每一列寫一次整張表：表上千列、一批上千封信＝平方慢，21 秒、Ctrl-C 33 秒才退）；
    // 對完再寫一次。fork 了、表還沒寫就被 kill -9 的，重開時 start 看小格裡活著的子 loop 接回（live_in_cell），不會同一格兩份
    auto last = Clock::now();
    auto some = [&] {
        if (Clock::now() - last >= std::chrono::milliseconds(FLUSH_MS)) {
            flush_table();
            last = Clock::now();
        }
    };
    for (auto& [n, spec] : want.items()) {
        auto at = index_.find(n);
        if (at != index_.end()) {
            Child& c = at->second->second;
            if (c.failed) {
                c.failed = false;   // 11-05：剛留成 stopped＋原因的，這圈不起；下一圈起 stopped 集合已有它
                continue;
            }
            if (c.held && stopped.count(n) == 0 && !(c.phase == "sleeping" && slept.count(n) > 0)) {   // 11-05：sleep 叫睡的不自己醒   // start（procs § 2c 第 3 條）／wake（sleeping 的列，11-03）：用列上的 stack 再起，ctl 不清（子 loop 比舊 state_flux 的 ctl_seq，已套用過的不重做）
                Child nc = start(n, spec, c.stack, c.ws, c.exec, c.def, c.limits, c.launch, c.auto_restart, c.restart_on_stuck, c.stuck_after_cycles, c.stuck_after_ms);   // 信箱接回只留名時照列上的值
                nc.revived = true;   // 11-05：REVIVE_MS 內退了＝留成 stopped＋原因（衝突 3）
                nc.revived_at = Clock::now();
                if (nc.auto_restart && c.phase == "sleeping") {
                    nc.quick_exits = c.quick_exits;   // 自動重起帶著連敗數；人 start（stopped）從零開始
                }
                if (c.phase == "sleeping") {
                    nc.stuck_restarts = c.stuck_restarts;
                }
                c = nc;
                log_child(n, c);
                some();
            }
            continue;
        }
        if (ended_.count(n) > 0 || (spec.is_null() && stopped.count(n) == 0)) {
            continue;
        }
        if (stopped.count(n) > 0 || slept.count(n) > 0) {   // add＋stop 同時（procs § 2c 第 2 條）：直接一列 stopped、不起、stack 不建
            Child c;
            c.phase = stopped.count(n) > 0 ? "stopped" : "sleeping";   // 11-05：add＋sleep 同時＝一列 sleeping、不起（wake 才起）
            c.held = true;
            c.own = false;
            c.launch = launch_of(spec, cwd_);
            c.auto_restart = auto_restart_of(spec);
            c.restart_on_stuck = ros_of(spec);
            c.stuck_after_cycles = spec.is_object() ? spec.value("stuck_after_cycles", 10LL) : 10;
            if (spec.is_object() && spec.contains("stuck_after_ms")) {
                c.stuck_after_ms = spec["stuck_after_ms"].get<long long>();
            }
            c.stack = cell_of(n, spec);
            c.exec = exec_of(spec, cwd_);
            c.def = def_of(spec);
            c.limits = limits_of(spec, Json());
            add(n, c);
        } else {
            Child nc = start(n, spec, cell_of(n, spec));
            nc.revived = true;   // 11-05 第二輪：add 剛起的也算（REVIVE_MS 內退＝「起不來」，原本寫成「跑到一半掛了」）
            nc.revived_at = Clock::now();
            add(n, nc);
        }
        some();   // 起一大批要好一陣子：每 FLUSH_MS 寫一次，讓人看得到進度
    }
    flush_table();
}


}  // namespace aos::daemon
