// child.cpp：【child】一支子 loop（說明見 child.hpp）。
//
// 10-21 傍晚起子 loop 經 aos-exec 起（使用者「5.要」，ideas § 9；`aos-exec -- 小格/loop.json#/_entry`）：
// daemon 把子項設定寫成小格裡的 loop.json、蓋上 "_entry": ["aos-loop", {"$env": "AOS_CF"}]，fork 一個子行程呼叫 aos-exec 的
// run_cli——它 cd 進小格、讀小格的 .env（若有）、exec 成 PATH 上的 aos-loop（指到 #/_entry，不受 $AOS_ENTRY 影響）。
// 所以 ps 看到的子 loop 叫 aos-loop（原本 fork 後在子行程裡直接跑 aos-loop 的 Loop、名字是 aos-daemon，那是 10-20 頂層代定的做法，換掉）。
// fork 時 daemon 只有一條執行緒，子行程裡做 C++ 配置、setenv 不會撞鎖。三個訊號 daemon 一開始就擋著（block_signals），
// 子行程 exec 之前解開（遮罩會跨 exec 繼承；子行程不擋）。
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

#include <fcntl.h>
#include <sys/wait.h>
#include <unistd.h>

namespace aos::daemon {

// 子行程：自成 session、接好三個串流、設 AOS_STACK、cd 到 daemon 的 cwd，`aos-exec -- 小格/loop.json#/_entry`。不回來。
[[noreturn]] static void run_child(const std::string& cell, const std::string& cwd, int err_fd) {
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
    if (chdir(cwd.c_str()) != 0) {
        std::fprintf(stderr, "aos-daemon: %s cd 不進 %s：%s\n", code::Internal, cwd.c_str(), std::strerror(errno));
    } else {
        rc = aos::exec::run_cli({"--", aos::join(cell, "loop.json") + "#/_entry"});   // exec 成功就不回來
    }
    std::fflush(nullptr);
    _exit(rc);
}

Child spawn(const std::string& name, const std::string& cell, const Json& spec, const std::string& cwd) {
    Json cfg;
    if (spec.is_object()) {
        cfg = spec;
    } else {
        cfg = Json::object();
        cfg["run"] = spec;
    }
    Json run = cfg.value("run", Json());   // 子 loop 經 aos-exec 起、cwd 會是小格：相對的目標照 daemon 的 cwd 轉成絕對（其他不動、不驗）
    if (run.is_string()) {
        cfg["run"] = aos::join(cwd, run.get<std::string>());
    } else if (run.is_array() && !run.empty() && run[0].is_string()) {
        cfg["run"][0] = aos::join(cwd, run[0].get<std::string>());
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
    std::error_code ec;
    std::filesystem::create_directory(cell, ec);   // 只建小格這一層：$AOS_STACK 不在＝建不了（建 stack 只在 aos-exec 做，N-59 第 1 件；10-23 前是 mkdir -p）
    if (ec) {
        throw Error{code::MkdirFailed, "起不了子項 " + name + "：建不了 " + cell + "（" + ec.message() + "）"};
    }
    try {
        aos::loop::write_window(aos::join(cell, "loop.json"), cfg);
    } catch (const Error& e) {
        throw Error{e.code, "起不了子項 " + name + "：" + e.msg};
    }
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
        run_child(cell, cwd, err_fd);
    }
    close(err_fd);
    Child c;
    c.pid = pid;
    c.started_at_ticks = aos::proc_started_at_ticks(pid);
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
    return r;
}

}  // namespace aos::daemon
