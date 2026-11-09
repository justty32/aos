// child.cpp：【child】建立小格、啟動子 loop 或 exec 型子項，並回收與輸出子項狀態（說明見 child.hpp）。
//
// 10-21 傍晚起子 loop 經 aos-exec 起（使用者「5.要」，ideas § 9；`aos-exec -- 小格/loop.json#/_entry`）：
// daemon 把子項設定寫成小格裡的 loop.json、蓋上 "_entry": ["aos-loop", {"$env": "AOS_CF"}]，fork 一個子行程呼叫 aos-exec 的
// run_cli——它 cd 進小格、讀小格的 .env（若有）、exec 成 PATH 上的 aos-loop（指到 #/_entry，不受 $AOS_ENTRY 影響）。
// 所以 ps 看到的子 loop 叫 aos-loop（原本 fork 後在子行程裡直接跑 aos-loop 的 Loop、名字是 aos-daemon，那是 10-20 頂層代定的做法，換掉）。
// fork 時 daemon 只有一條執行緒，子行程裡做 C++ 配置、setenv 不會撞鎖。三個訊號 daemon 一開始就擋著（block_signals），
// 子行程 exec 之前還原 block_signals 前的遮罩（遮罩會跨 exec 繼承；含 daemon 額外擋住的訊號）。
// 11-03（thinking 2026-11-03-procs）：loops／execs 統稱 procs；小格＝proc 的 stack（寫了 stack＝它，沒寫＝$AOS_STACK/procs/<名字>/）。
// 10-30 execs（thinking 2026-10-30-agent-lifecycle B-12 ②、使用者「讓daemon可以掛aos-exec，也是不錯的」）：exec 型子項走同一條 launch
// （小格、stderr.txt、setsid、/dev/null、AOS_STACK、cd 到 daemon 的 cwd），只是不寫 loop.json、run_cli 直接拿 {"--", 目標, 參數...}——中間沒有 aos-loop。
// 10-30 eca（thinking 2026-10-30-eca 衝突 1，使用者「都照建議」；N-55 工作區由呼叫方設，daemon 是呼叫方）：子項寫了 ws＝run_child 多設 AOS_WS；
// 沒寫＝不碰（繼承 daemon 的）。
// 11-02（resident-bob 衝突 2、daemon-env 方向題 2，使用者「照建議走」）：兩種子項一律多設 AOS_DAEMON＝daemon 的 stack（絕對、結尾 /；
// 11-04 晚改名，舊名不認，使用者要「直接簡化成AOS_DAEMON」），
// 兄弟（控制器與 bob）靠它找到共同的 stack；只設這一個（定義資料夾、ws 那兩名不設）。
#include "child/child.hpp"
#include "child/limits.hpp"

#include "aos/util/files.hpp"
#include "aos/util/proc.hpp"
#include "aos/util/signals.hpp"

#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <filesystem>
#include <system_error>
#include <vector>

#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

namespace aos::daemon {

// 子行程：自成 session、接好三個串流、設 AOS_STACK、cd 到 daemon 的 cwd，呼叫 aos-exec 的 run_cli(argv)。不回來。
// argv：子 loop＝{"--", 小格/loop.json#/_entry}；exec 型子項＝{"--", 目標, 參數...}（10-30）。fork 之前就備好。
// ws：空＝AOS_WS 不碰（繼承 daemon 的）；不空＝設成它（eca 10-30）。
// dstack：daemon 的 stack（絕對、結尾 /），一律設成 AOS_DAEMON（11-02，resident-bob 衝突 2：兄弟要共用位置；只設這一個；11-04 晚改名）。
// lim：份額（fork 之前 prep_limits 備好）；接好 stderr 之後、run_cli 之前照做（11-05 feat-proto 件 5，失敗＝stderr.txt 一行 LimitBad、退 1）。
[[noreturn]] static void run_child(const std::string& cell, const std::string& cwd, int err_fd,
                                   const std::vector<std::string>& argv, const std::string& ws, const std::string& dstack,
                                   const Limits& lim) {
    setsid();
    int null_fd = open("/dev/null", O_RDWR);
    if (null_fd >= 0) {
        dup2(null_fd, 0);
        dup2(null_fd, 1);
        if (null_fd > 2) {
            close(null_fd);
        }
    }
    dup2(err_fd, 2);
    if (err_fd > 2) {
        close(err_fd);
    }
    apply_limits(lim);   // 等同 s6-softlimit／s6-setuidgid（daemon 自己做、不 exec s6）；proc 自己不知道（「偷偷」，C-52）
    aos::restore_signals();
    int rc = 1;
    setenv("AOS_STACK", (cell + "/").c_str(), 1);
    setenv("AOS_DAEMON", dstack.c_str(), 1);
    if (!ws.empty()) {
        setenv("AOS_WS", ws.c_str(), 1);
    }
    if (chdir(cwd.c_str()) != 0) {
        std::fprintf(stderr, "aos-daemon: error: %s cannot cd into %s: %s\n", code::Internal, cwd.c_str(), std::strerror(errno));
    } else {
        rc = aos::exec::run_cli(argv);   // exec 成功就不回來
    }
    std::fflush(nullptr);
    _exit(rc);
}

// 預設小格（deep＝false）只建 procs/ 與小格這兩層：$AOS_STACK 不在＝建不了（建 stack 只在 aos-exec 做，N-59 第 1 件）；procs/ 是 daemon 自己的固定名，有就沿用。
// proc 自己寫了 stack（deep＝true，11-03 procs § 2b）＝mkdir -p（不在就建，同 aos-exec --stack）。spawn 與 spawn_exec 共用。
static void make_cell(const std::string& name, const std::string& cell, bool deep) {
    std::error_code ec;
    if (deep) {
        std::filesystem::create_directories(cell, ec);
    } else {
        std::filesystem::create_directory(std::filesystem::path(cell).parent_path(), ec);
        if (!ec) {
            std::filesystem::create_directory(cell, ec);
        }
    }
    if (ec) {
        throw Error{code::MkdirFailed, "cannot start child " + name + ": cannot create " + cell + " (" + ec.message() + ")"};
    }
}

// 小格建好之後：開小格的 stderr.txt（附加）、fork、子行程 run_child(argv, ws, dstack)。spawn 與 spawn_exec 共用。ws＝null 或絕對路徑（記進 Child）。
static Child launch(const std::string& name, const std::string& cell, const std::string& cwd,
                    const std::vector<std::string>& argv, const Json& ws, const std::string& dstack, const std::string& err_name,
                    const Json& limits) {
    std::string ws_s = ws.is_string() ? ws.get<std::string>() : std::string();   // fork 之前備好
    Limits lim = prep_limits(limits);
    std::string err_path = aos::join(cell, err_name);
    int err_fd = open(err_path.c_str(), O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
    if (err_fd < 0) {
        throw Error{code::LaunchFailed, "cannot start child " + name + ": cannot open " + err_path + " (" + std::strerror(errno) + ")"};
    }
    struct stat est {};
    long long err_off = fstat(err_fd, &est) == 0 ? (long long)est.st_size : 0;
    std::fflush(nullptr);
    pid_t pid = fork();
    if (pid < 0) {
        int e = errno;
        close(err_fd);
        throw Error{code::LaunchFailed, "cannot start child " + name + ": fork failed (" + std::strerror(e) + ")"};
    }
    if (pid == 0) {
        run_child(cell, cwd, err_fd, argv, ws_s, dstack, lim);
    }
    close(err_fd);
    Child c;
    Json target = std::vector<std::string>(argv.begin() + 1, argv.end());
    target[0] = aos::abspath(aos::join(cwd, target[0].get<std::string>()));
    c.launch = Json::object({{"exec", target}});
    c.pid = pid;
    c.started_at_ticks = aos::proc_started_at_ticks(pid);
    c.err_off = err_off;
    c.ws = ws_s.empty() ? Json() : Json(ws_s);
    c.stack = cell;
    c.limits = limits.is_object() && !limits.empty() ? limits : Json();
    return c;
}

// 內嵌單子搬進小格之前（10-24；11-02 晚 exec 型子項也用）：跑它時相對路徑的基準是小格（AOS_CD），所以 cwd 照 daemon 的 cwd 定死——
// 沒寫＝daemon 的 cwd、相對的字串＝接在 daemon 的 cwd 後面（argv[0]、stdin／stdout／stderr 都從 cwd 算，跟著對）；
// cwd 是指示詞就不動（解出來若是相對的，從小格算）。裡面相對的 $ref 已在 read_procs 轉成絕對。
static void pin_cwd(Json& inst, const std::string& cwd, const std::string& cell, const std::string& dstack) {
    Json c = inst.value("cwd", Json());
    if (c.is_null()) {
        inst["cwd"] = daemon_ref(cwd, dstack);   // 11-05：存相對 daemon 的 stack（指示詞），搬家後由 aos-exec 從新的 AOS_DAEMON 拼回
    } else if (c.is_string()) {
        inst["cwd"] = daemon_ref(aos::abspath(aos::join(cwd, c.get<std::string>())), dstack);
    }
    inst = rel_refs(inst, cell);
}

Child spawn(const std::string& name, const std::string& cell, bool deep, const Json& spec, const std::string& cwd,
            const std::string& dstack, const CellNames& names, const Json& limits, const Json& kept_ws) {
    std::string lj = aos::join(cell, names.loop);
    if (spec.is_null()) {   // 信箱接回的 stopped／sleeping 列（只留名、沒有設定）再 start／wake：照小格裡現有的 loop.json（11-03），ws 照列上記的（11-03 晚）
        make_cell(name, cell, deep);
        return launch(name, cell, cwd, {"--", lj + "#/_entry"}, kept_ws, dstack, names.err, limits);
    }
    Json cfg = spec;
    Json ws = cfg.value("ws", Json());   // ws、stack 是 daemon 的 key（不是 loop 的）：不灌進小格的 loop.json；ws 只進子行程的環境（AOS_WS）
    cfg.erase("ws");
    cfg.erase("stack");
    cfg.erase("def");   // def 同（11-04）：只記進表
    cfg.erase("limits");   // limits 同（11-05 feat-proto 件 5）：daemon 在子行程裡做，子 loop 不知道
    cfg.erase("stuck_after_cycles");
    cfg.erase("auto_restart");   // 11-06（no-pid P6）：通用重起旗標只歸 daemon 管
    cfg.erase("restart_on_stuck");
    Json ex = cfg.value("exec", Json());   // 子 loop 經 aos-exec 起、cwd 會是小格：相對的目標照 daemon 的 cwd 轉成絕對（其他不動、不驗；單子見下）
    // 11-05（portable-flow 03 推薦 (b)）：轉絕對之後寫成 {"$env": "AOS_DAEMON", "$path": 相對 daemon 的 stack}，aos-loop 解指示詞拼回（搬家不用改檔）
    auto keep = [&](const std::string& t) {
        return t.empty() || t[0] == '#' ? Json(t) : daemon_ref(aos::abspath(aos::join(cwd, t.substr(0, t.find('#')))) +
                                                                   (t.find('#') == std::string::npos ? "" : t.substr(t.find('#'))), dstack);
    };
    if (ex.is_string()) {
        cfg["exec"] = keep(ex.get<std::string>());
    } else if (ex.is_array() && !ex.empty() && ex[0].is_string()) {
        cfg["exec"][0] = keep(ex[0].get<std::string>());
    } else if (ex.is_object()) {
        pin_cwd(cfg["exec"], cwd, cell, dstack);   // 內嵌單子（10-24）
    }
    // ctl／state 不補（11-04，four-elements 08 步 6「不補名」）：aos-loop 自己沒寫＝ctl.json／state.json、null＝不開
    Json exec_entry = Json::array();
    exec_entry.push_back("aos-loop");
    exec_entry.push_back(Json::object({{"$env", "AOS_CF"}}));
    cfg["_entry"] = exec_entry;   // 一律蓋上
    make_cell(name, cell, deep);
    try {
        aos::loop::write_window(lj, cfg);
    } catch (const Error& e) {
        throw Error{e.code, "cannot start child " + name + ": " + e.msg};
    }
    return launch(name, cell, cwd, {"--", lj + "#/_entry"}, ws, dstack, names.err, limits);
}

Child spawn_exec(const std::string& name, const std::string& cell, bool deep, const Json& spec, const std::string& cwd,
                 const std::string& dstack, const CellNames& names, const Json& limits) {
    // 字串、陣列＝目標本身；物件＝{"exec": 目標或單子, "ws"?, "stack"?}（read_procs 驗過）
    const Json& target = spec.is_object() ? spec["exec"] : spec;
    Json ws = spec.is_object() ? spec.value("ws", Json()) : Json();
    std::vector<std::string> argv{"--"};   // 相對的目標不轉：子行程 cd 到 daemon 的 cwd 才叫 aos-exec，本來就從那裡算
    if (target.is_object()) {
        // 內嵌單子（11-02 晚，使用者「6.要」）：同子 loop 的單子搬進小格——寫成小格的 exec.json {"exec": 單子}（cwd 定成 daemon 的 cwd），
        // 子行程 `aos-exec -- 小格/exec.json#/exec` 跑它一次：AOS_CF＝小格的 exec.json、AOS_CO＝/exec（同 loop 型的小格 loop.json#/exec）。
        // 單子沒寫 stdin／stdout＝照舊接 daemon 給的 /dev/null、stderr 是小格的 stderr.txt；寫了就照它
        Json inst = target;
        pin_cwd(inst, cwd, cell, dstack);
        make_cell(name, cell, deep);
        try {
            aos::loop::write_window(aos::join(cell, names.exec), Json::object({{"exec", inst}}));
        } catch (const Error& e) {
            throw Error{e.code, "cannot start child " + name + ": " + e.msg};
        }
        Child c = launch(name, cell, cwd, {"--", aos::join(cell, names.exec) + "#/exec"}, ws, dstack, names.err, limits);
        return c;
    }
    if (target.is_string()) {
        argv.push_back(target.get<std::string>());
    } else {
        for (const Json& a : target) {
            argv.push_back(a.get<std::string>());
        }
    }
    make_cell(name, cell, deep);
    Child c = launch(name, cell, cwd, argv, ws, dstack, names.err, limits);
    return c;
}

std::string ctl_name(const std::string& cell, const CellNames& names) {
    auto cfg = aos::read_json(aos::join(cell, names.loop));
    Json ctl = cfg && cfg->is_object() ? cfg->value(aos::loop::CtlWindow::config_key, Json()) : Json();
    return ctl.is_string() && !ctl.get<std::string>().empty() ? ctl.get<std::string>() : aos::loop::CtlWindow::default_name;
}

bool alive(Child& c) {
    if (!c.own) {
        return c.started_at_ticks.has_value() && aos::proc_started_at_ticks(c.pid) == c.started_at_ticks;
    }
    if (c.reaped) {
        return false;
    }
    int status = 0;
    pid_t got = waitpid(c.pid, &status, WNOHANG);
    if (got == 0) {
        return true;
    }
    c.reaped = true;
    if (got == c.pid) {
        if (WIFSIGNALED(status)) {
            c.signal = WTERMSIG(status);
            c.code = 128 + WTERMSIG(status);
        } else {
            c.code = WEXITSTATUS(status);
        }
    }
    return false;
}

Json row(const Child& c, const std::string& dstack) {
    Json r = Json::object();
    r["pid"] = c.held ? Json() : Json((long long)c.pid);   // stopped／sleeping 的列：行程不在（11-03）
    r["started_at_ticks"] = nullptr;
    if (c.started_at_ticks) {
        r["started_at_ticks"] = *c.started_at_ticks;
    }
    r["phase"] = c.stuck && c.phase == "running" ? "stuck" : c.phase;
    r["code"] = c.code;
    r["signal"] = c.signal;
    auto rel = [&](const Json& v) { return v.is_string() ? Json(rel_spec(v.get<std::string>(), dstack)) : v; };
    r["stack"] = rel_spec(c.stack, dstack);   // 11-05：相對 daemon 的 stack（portable-flow）   // 11-03 procs § 2b：一律寫（adopt、start、aos-daemon-ctl where 靠它）
    if (!c.ws.is_null()) {
        r["ws"] = rel(c.ws);   // eca 10-30：有給才寫
    }
    r["launch"] = c.launch;
    if (c.launch.is_object()) {
        Json target = c.launch.value("exec", Json());
        if (target.is_string()) {
            r["launch"]["exec"] = rel(target);
        } else if (target.is_array() && !target.empty()) {
            r["launch"]["exec"][0] = rel(target[0]);
        }
        for (const char* key : {"ws", "stack", "def"}) {
            if (c.launch.contains(key)) {
                r["launch"][key] = rel(c.launch[key]);
            }
        }
        r["launch"] = rel_refs(r["launch"], dstack);
    }
    if (c.phase == "stopping") {
        r["stop_mode"] = c.soft ? "stop" : c.nap ? "sleep" : "remove";
    }
    r["exec"] = rel(c.exec);   // 11-04 晚（aos-agent 方向題 1）：一律寫，目標（絕對）或 null
    r["def"] = rel(c.def);     // 11-04（使用者「那就b。」）：一律寫，定義資料夾或 null（11-05 起相對 daemon 的 stack）
    r["reason"] = c.stuck && c.phase == "running" ? Json("control window has not been answered within " + std::to_string(c.stuck_after_cycles) + " cycles") : c.reason;    // 11-05（portable-flow 衝突 3）：null 或 daemon 把它留成 stopped 的原因
    if (!c.limits.is_null()) {
        r["limits"] = c.limits;   // 11-05（feat-proto 件 5）：生效的份額，有才寫
    }
    if (c.auto_restart) {
        r["auto_restart"] = true;
    }
    if (c.stuck_after_cycles != 10) {
        r["stuck_after_cycles"] = c.stuck_after_cycles;   // P7：不是預設 10 才寫，adopt 沒這欄＝10
    }
    if (c.restart_on_stuck) {
        r["restart_on_stuck"] = true;
    }
    return r;
}

}  // namespace aos::daemon
