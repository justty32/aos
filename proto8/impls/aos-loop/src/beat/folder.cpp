// folder.cpp：【beat】run_folder——`aos-exec -- 目標 參數...`，在 fork 出來的子行程裡呼叫 aos-exec 的 run_cli。
//
//   1. 擋住 SIGCHLD（那三個訊號 block_signals 已擋）、開 signalfd，再 fork
//   2. 子行程：關掉 signalfd、解開四個訊號，aos::exec::run_cli（定工作區、找入口、讀 .env、cd、開跑——可執行檔／argv 陣列是 exec；
//      inst 單子在這個子行程裡跑、回來以子程式的碼 _exit）。它自己的錯印一行「aos-exec: 代號 原因」、_exit(1)
//      （同 Python 版 aos-exec 子程序退 1）。每拍重找，入口改了下一拍就生效
//   3. 這個行程：poll signalfd——三個訊號 kill 給子行程（記下第一個）；SIGCHLD 就 waitpid 看是不是它結束了
//
// 為什麼在子行程裡呼叫、不 exec 一支 aos-exec：impls 的 aos-exec 是函式庫＋命令列（ideas § 20「aos-exec 的公開 api」），
// 呼叫它的 run_cli 就是同一件事，也不必在 PATH 上找 aos-exec。（10-21 起 .env 要在挑入口之前讀、要 cd、要 setenv，
// 原本「這個行程算好入口、子行程 apply_env＋launch」拆不開了，整段搬進子行程。）
// fork 之後在子行程裡做 C++ 配置、setenv：呼叫者是單執行緒（run_inst 的工人執行緒在它回來前就 join 了），
// fork 出來的子行程只有這一條執行緒，不會撞到別條執行緒握著的鎖，所以安全。
// 子行程跟呼叫者同一個行程群組（不另開）：同 Python 版 subprocess.call，終端機的 Ctrl-C 兩個都收得到（CONVENTION P-36）。
#include "beat/beat.hpp"

#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>

#include <poll.h>
#include <sys/signalfd.h>
#include <sys/wait.h>
#include <unistd.h>

namespace aos::loop {

using Clock = std::chrono::steady_clock;

namespace {

// 那三個訊號＋SIGCHLD。
sigset_t beat_signals() {
    sigset_t set = the_signals();
    sigaddset(&set, SIGCHLD);
    return set;
}

// 這拍期間擋住 SIGCHLD（出去還原；那三個訊號由 block_signals 一直擋著）。
struct ChldMask {
    sigset_t old;
    ChldMask() {
        sigset_t set;
        sigemptyset(&set);
        sigaddset(&set, SIGCHLD);
        sigprocmask(SIG_BLOCK, &set, &old);
    }
    ~ChldMask() { sigprocmask(SIG_SETMASK, &old, nullptr); }
    ChldMask(const ChldMask&) = delete;
    ChldMask& operator=(const ChldMask&) = delete;
};

struct Fd {
    int fd;
    explicit Fd(int f) : fd(f) {}
    ~Fd() {
        if (fd >= 0) {
            close(fd);
        }
    }
    Fd(const Fd&) = delete;
    Fd& operator=(const Fd&) = delete;
};

unsigned long long ms_since(Clock::time_point t0) {
    long long us = std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - t0).count();
    return (unsigned long long)((us + 500) / 1000);   // 四捨五入（Python 版 round(秒 × 1000)）
}

// 子行程：一支 aos-exec。不回來。
[[noreturn]] void child(const std::vector<std::string>& argv, int sig_fd) {
    close(sig_fd);
    sigset_t set = beat_signals();
    sigprocmask(SIG_UNBLOCK, &set, nullptr);
    int rc = aos::exec::run_cli(argv);   // exec 成功就不回來；inst 單子回子程式的碼；自己的錯已印好、回 1
    std::fflush(nullptr);
    _exit(rc);
}

// 等子行程結束；期間收到的三個訊號 kill 給它。回 waitpid 的 status，received 記第一個。
int wait_forwarding(pid_t pid, int sig_fd, int& received) {
    while (true) {
        pollfd p{sig_fd, POLLIN, 0};
        int r = poll(&p, 1, -1);
        if (r < 0 && errno == EINTR) {
            continue;
        }
        signalfd_siginfo info;
        if (read(sig_fd, &info, sizeof info) != (ssize_t)sizeof info) {
            continue;
        }
        int sig = (int)info.ssi_signo;
        if (sig != SIGCHLD) {
            if (received == 0) {
                received = sig;
            }
            kill(pid, sig);   // 它已經結束（ESRCH）就算了
            continue;
        }
        int status = 0;
        pid_t got = waitpid(pid, &status, WNOHANG);
        if (got == pid) {
            return status;
        }
    }
}

}  // namespace

Beat run_folder(const std::vector<std::string>& argv) {
    Clock::time_point t0 = Clock::now();
    Beat b;

    // 1. 訊號
    ChldMask mask;
    sigset_t set = beat_signals();
    Fd sig_fd(signalfd(-1, &set, SFD_CLOEXEC));
    if (sig_fd.fd < 0) {
        throw Error{code::Internal, std::string("準備轉送訊號失敗：") + std::strerror(errno)};
    }

    // 2. fork
    std::fflush(nullptr);
    pid_t pid = fork();
    if (pid < 0) {
        throw Error{code::LaunchFailed, std::string("fork 失敗：") + std::strerror(errno)};
    }
    if (pid == 0) {
        child(argv, sig_fd.fd);
    }

    // 3. 等
    int status = wait_forwarding(pid, sig_fd.fd, b.received);
    if (WIFSIGNALED(status)) {
        b.signal = WTERMSIG(status);
        b.code = 128 + b.signal;
    } else {
        b.code = WEXITSTATUS(status);
    }
    b.ms = ms_since(t0);
    return b;
}

}  // namespace aos::loop
