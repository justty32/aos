// child.cpp：【child】一支子 loop，或一個 exec 型子項（說明見 child.hpp）。
//
// 10-21 傍晚起子 loop 經 aos-exec 起（使用者「5.要」，ideas § 9；`aos-exec -- 小格/loop.json#/_entry`）：
// daemon 把子項設定寫成小格裡的 loop.json、蓋上 "_entry": ["aos-loop", {"$env": "AOS_CF"}]，fork 一個子行程呼叫 aos-exec 的
// run_cli——它 cd 進小格、讀小格的 .env（若有）、exec 成 PATH 上的 aos-loop（指到 #/_entry，不受 $AOS_ENTRY 影響）。
// 所以 ps 看到的子 loop 叫 aos-loop（原本 fork 後在子行程裡直接跑 aos-loop 的 Loop、名字是 aos-daemon，那是 10-20 頂層代定的做法，換掉）。
// fork 時 daemon 只有一條執行緒，子行程裡做 C++ 配置、setenv 不會撞鎖。三個訊號 daemon 一開始就擋著（block_signals），
// 子行程 exec 之前解開（遮罩會跨 exec 繼承；子行程不擋）。
// 10-30 execs（thinking 2026-10-30-agent-lifecycle B-12 ②、使用者「讓daemon可以掛aos-exec，也是不錯的」）：exec 型子項走同一條 launch
// （小格、stderr.txt、setsid、/dev/null、AOS_STACK、cd 到 daemon 的 cwd），只是不寫 loop.json、run_cli 直接拿 {"--", 目標, 參數...}——中間沒有 aos-loop。
// 10-30 eca（thinking 2026-10-30-eca 衝突 1，使用者「都照建議」；N-55 工作區由呼叫方設，daemon 是呼叫方）：子項寫了 ws＝run_child 多設 AOS_WS；
// 沒寫＝不碰（繼承 daemon 的）。
#include "child/child.hpp"

#include "aos/files.hpp"
#include "aos/proc.hpp"

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
#include <sys/wait.h>
#include <unistd.h>

namespace aos::daemon {

// 子行程：自成 session、接好三個串流、設 AOS_STACK、cd 到 daemon 的 cwd，呼叫 aos-exec 的 run_cli(argv)。不回來。
// argv：子 loop＝{"--", 小格/loop.json#/_entry}；exec 型子項＝{"--", 目標, 參數...}（10-30）。fork 之前就備好。
// ws：空＝AOS_WS 不碰（繼承 daemon 的）；不空＝設成它（eca 10-30）。
[[noreturn]] static void run_child(const std::string& cell, const std::string& cwd, int err_fd,
                                   const std::vector<std::string>& argv, const std::string& ws) {
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
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGINT);
    sigaddset(&set, SIGTERM);
    sigaddset(&set, SIGHUP);
    sigprocmask(SIG_UNBLOCK, &set, nullptr);
    int rc = 1;
    setenv("AOS_STACK", (cell + "/").c_str(), 1);
    if (!ws.empty()) {
        setenv("AOS_WS", ws.c_str(), 1);
    }
    if (chdir(cwd.c_str()) != 0) {
        std::fprintf(stderr, "aos-daemon: %s cd 不進 %s：%s\n", code::Internal, cwd.c_str(), std::strerror(errno));
    } else {
        rc = aos::exec::run_cli(argv);   // exec 成功就不回來
    }
    std::fflush(nullptr);
    _exit(rc);
}

// 只建小格這一層：$AOS_STACK 不在＝建不了（建 stack 只在 aos-exec 做，N-59 第 1 件；10-23 前是 mkdir -p）。spawn 與 spawn_exec 共用。
static void make_cell(const std::string& name, const std::string& cell) {
    std::error_code ec;
    std::filesystem::create_directory(cell, ec);
    if (ec) {
        throw Error{code::MkdirFailed, "起不了子項 " + name + "：建不了 " + cell + "（" + ec.message() + "）"};
    }
}

// 小格建好之後：開小格的 stderr.txt（附加）、fork、子行程 run_child(argv, ws)。spawn 與 spawn_exec 共用。ws＝null 或絕對路徑（記進 Child）。
static Child launch(const std::string& name, const std::string& cell, const std::string& cwd,
                    const std::vector<std::string>& argv, const Json& ws) {
    std::string ws_s = ws.is_string() ? ws.get<std::string>() : std::string();   // fork 之前備好
    std::string err_path = aos::join(cell, "stderr.txt");
    int err_fd = open(err_path.c_str(), O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
    if (err_fd < 0) {
        throw Error{code::LaunchFailed, "起不了子項 " + name + "：開不了 " + err_path + "（" + std::strerror(errno) + "）"};
    }
    std::fflush(nullptr);
    pid_t pid = fork();
    if (pid < 0) {
        int e = errno;
        close(err_fd);
        throw Error{code::LaunchFailed, "起不了子項 " + name + "：fork 失敗（" + std::strerror(e) + "）"};
    }
    if (pid == 0) {
        run_child(cell, cwd, err_fd, argv, ws_s);
    }
    close(err_fd);
    Child c;
    c.pid = pid;
    c.started_at_ticks = aos::proc_started_at_ticks(pid);
    c.ws = ws_s.empty() ? Json() : Json(ws_s);
    return c;
}

Child spawn(const std::string& name, const std::string& cell, const Json& spec, const std::string& cwd) {
    Json cfg;
    if (spec.is_object()) {
        cfg = spec;
    } else {
        cfg = Json::object();
        cfg["exec"] = spec;
    }
    Json ws = cfg.value("ws", Json());   // eca 10-30：不是 loop 的 key，不灌進小格的 loop.json，只進子行程的環境（AOS_WS）
    cfg.erase("ws");
    Json ex = cfg.value("exec", Json());   // 子 loop 經 aos-exec 起、cwd 會是小格：相對的目標照 daemon 的 cwd 轉成絕對（其他不動、不驗；單子見下）
    if (ex.is_string()) {
        cfg["exec"] = aos::join(cwd, ex.get<std::string>());
    } else if (ex.is_array() && !ex.empty() && ex[0].is_string()) {
        cfg["exec"][0] = aos::join(cwd, ex[0].get<std::string>());
    } else if (ex.is_object()) {
        // 內嵌單子（10-24）：子 loop 跑它時相對路徑的基準是小格（AOS_CD），所以 cwd 照 daemon 的 cwd 定死——
        // 沒寫＝daemon 的 cwd、相對的字串＝接在 daemon 的 cwd 後面（argv[0]、stdin／stdout／stderr 都從 cwd 算，跟著對）；
        // cwd 是指示詞就不動（解出來若是相對的，從小格算）。裡面相對的 $ref 已在 read_loops 轉成絕對。
        Json c = ex.value("cwd", Json());
        if (c.is_null()) {
            cfg["exec"]["cwd"] = cwd;
        } else if (c.is_string()) {
            cfg["exec"]["cwd"] = aos::join(cwd, c.get<std::string>());
        }
    }
    if (!cfg.contains("ctl")) {
        cfg["ctl"] = "ctl.json";
    }
    if (!cfg.contains("state")) {
        cfg["state"] = "state.json";
    }
    Json exec_entry = Json::array();
    exec_entry.push_back("aos-loop");
    exec_entry.push_back(Json::object({{"$env", "AOS_CF"}}));
    cfg["_entry"] = exec_entry;   // 一律蓋上
    make_cell(name, cell);
    try {
        aos::loop::write_window(aos::join(cell, "loop.json"), cfg);
    } catch (const Error& e) {
        throw Error{e.code, "起不了子項 " + name + "：" + e.msg};
    }
    return launch(name, cell, cwd, {"--", aos::join(cell, "loop.json") + "#/_entry"}, ws);
}

Child spawn_exec(const std::string& name, const std::string& cell, const Json& spec, const std::string& cwd) {
    // 寫了 ws 的子項，read_execs 收成 {"exec": 目標, "ws": 絕對路徑}（eca 10-30）；沒寫＝目標本身
    const Json& target = spec.is_object() ? spec["exec"] : spec;
    Json ws = spec.is_object() ? spec.value("ws", Json()) : Json();
    std::vector<std::string> argv{"--"};   // 相對的目標不轉：子行程 cd 到 daemon 的 cwd 才叫 aos-exec，本來就從那裡算
    if (target.is_string()) {
        argv.push_back(target.get<std::string>());
    } else {
        for (const Json& a : target) {
            argv.push_back(a.get<std::string>());
        }
    }
    make_cell(name, cell);
    Child c = launch(name, cell, cwd, argv, ws);
    c.once = true;
    return c;
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

Json row(const Child& c) {
    Json r = Json::object();
    r["pid"] = (long long)c.pid;
    r["started_at_ticks"] = nullptr;
    if (c.started_at_ticks) {
        r["started_at_ticks"] = *c.started_at_ticks;
    }
    r["phase"] = c.phase;
    r["code"] = c.code;
    r["signal"] = c.signal;
    if (!c.ws.is_null()) {
        r["ws"] = c.ws;   // eca 10-30：有給才寫（沒給不寫這欄：列的形狀跟 10-30 前一樣，舊的讀者不受影響）
    }
    return r;
}

}  // namespace aos::daemon
