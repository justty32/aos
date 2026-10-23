// proc.cpp：【aos-util】子程序：起、看結束了沒、整群送訊號、收屍、/proc 資訊、memfd（說明見 include/aos/proc.hpp）。
#include "aos/error.hpp"
#include "aos/proc.hpp"

#include <cerrno>
#include <cstdio>
#include <ctime>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>

#include <signal.h>
#include <spawn.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

extern char** environ;

namespace aos {

// posix_spawn：一次做完「fork＋把 fd 接好＋exec」，比自己寫 fork／exec 短、也不會有 fork 後的各種陷阱。
pid_t spawn(const std::vector<std::string>& argv, Stdio io, bool new_session) {
    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    // dup2：子程序的 0／1／2 號 fd 換成我們給的（給 -1＝不動，沿用我們自己的）
    int targets[3] = {io.in, io.out, io.err};
    for (int i = 0; i < 3; ++i) {
        if (targets[i] >= 0) {
            posix_spawn_file_actions_adddup2(&actions, targets[i], i);
        }
    }

    posix_spawnattr_t attr;
    posix_spawnattr_init(&attr);
    sigset_t none;
    sigemptyset(&none);
    posix_spawnattr_setsigmask(&attr, &none);   // 我們擋著 INT／TERM／HUP（signals.cpp），子程序不要跟著擋
    short flags = POSIX_SPAWN_SETSIGMASK;
    if (new_session) {
        flags |= POSIX_SPAWN_SETSID;            // setsid：自成一個 session＝新群組，群組號碼＝它的 pid
    }
    posix_spawnattr_setflags(&attr, flags);

    std::vector<char*> args;
    for (const std::string& a : argv) {
        args.push_back(const_cast<char*>(a.c_str()));
    }
    args.push_back(nullptr);

    pid_t pid = 0;
    int rc = posix_spawn(&pid, argv[0].c_str(), &actions, &attr, args.data(), environ);
    posix_spawn_file_actions_destroy(&actions);
    posix_spawnattr_destroy(&attr);
    if (rc != 0) {
        throw Error{code::LaunchFailed, "起不了 " + argv[0] + "：" + std::strerror(rc)};
    }
    return pid;
}

bool has_exited(pid_t pid) {
    siginfo_t info{};
    // WNOHANG＝不等、WNOWAIT＝不收屍（只看）。沒結束時 si_pid 留 0。
    if (waitid(P_PID, (id_t)pid, &info, WEXITED | WNOHANG | WNOWAIT) != 0) {
        return errno != EINTR;   // 照理不會發生（不是我們的子程序）；當成結束了，免得卡住
    }
    return info.si_pid != 0;
}

void wait_exited(pid_t pid) {
    siginfo_t info{};
    while (waitid(P_PID, (id_t)pid, &info, WEXITED | WNOWAIT) != 0 && errno == EINTR) {
    }
}

void signal_group(pid_t pgid, int sig) {
    if (pgid > 0) {
        killpg(pgid, sig);   // 群組不在（ESRCH）、沒權限（EPERM）都不管
    }
}

int wait_plain(pid_t pid) {
    int status = 0;
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {
    }
    if (WIFSIGNALED(status)) {
        return -WTERMSIG(status);
    }
    return WEXITSTATUS(status);
}

int reap(pid_t pid) {
    signal_group(pid, SIGKILL);   // 還沒收屍，群組號碼不會被別人拿走：放心整群補一發清孫程式
    return wait_plain(pid);
}

int stop(pid_t pid) {
    signal_group(pid, SIGTERM);
    wait_exited(pid);
    return reap(pid);
}

std::optional<long long> proc_start_ticks(pid_t pid) {
    std::string path = "/proc/" + std::to_string(pid) + "/stat";
    if (pid == 0) {
        path = "/proc/self/stat";
    }
    std::ifstream f(path);
    std::string text((std::istreambuf_iterator<char>(f)), {});
    // 第 2 欄是程式名，用括號包著、裡面可能有空白，所以從最後一個 ')' 之後開始數：之後第 1 個是第 3 欄……第 20 個是第 22 欄
    size_t close_paren = text.rfind(')');
    if (close_paren == std::string::npos) {
        return std::nullopt;
    }
    std::istringstream rest(text.substr(close_paren + 1));
    std::string field;
    for (int i = 0; i < 20; ++i) {
        if (!(rest >> field)) {
            return std::nullopt;
        }
    }
    try {
        return std::stoll(field);
    } catch (const std::exception&) {
        return std::nullopt;
    }
}

std::string utc_now_ms() {
    timespec ts{};
    clock_gettime(CLOCK_REALTIME, &ts);
    std::tm tm{};
    gmtime_r(&ts.tv_sec, &tm);
    char day[32];
    std::strftime(day, sizeof day, "%Y-%m-%dT%H:%M:%S", &tm);
    char buf[80];
    std::snprintf(buf, sizeof buf, "%s.%03ld+00:00", day, ts.tv_nsec / 1000000L);
    return buf;
}

std::optional<std::string> boot_id() {
    std::ifstream f("/proc/sys/kernel/random/boot_id");
    std::string id;
    if (!(f >> id)) {
        return std::nullopt;
    }
    return id;
}

std::string sibling_tool(const std::string& name) {
    namespace fs = std::filesystem;
    fs::path me = fs::read_symlink("/proc/self/exe");             // impls/X/bin/X
    fs::path impls = me.parent_path().parent_path().parent_path();   // impls
    return (impls / name / "bin" / name).string();
}

int memfd_empty() {
    int fd = memfd_create("aos", MFD_CLOEXEC);
    if (fd < 0) {
        throw Error{code::Internal, std::string("memfd_create 失敗：") + std::strerror(errno)};
    }
    return fd;
}

int memfd_with(const std::string& text) {
    int fd = memfd_empty();
    size_t done = 0;
    while (done < text.size()) {
        ssize_t n = write(fd, text.data() + done, text.size() - done);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n < 0) {
            close(fd);
            throw Error{code::Internal, std::string("寫 memfd 失敗：") + std::strerror(errno)};
        }
        done += (size_t)n;
    }
    lseek(fd, 0, SEEK_SET);   // 讀寫位置回到開頭：子程序從頭讀
    return fd;
}

std::string read_all(int fd) {
    std::string text;
    char buf[65536];
    lseek(fd, 0, SEEK_SET);
    while (true) {
        ssize_t n = read(fd, buf, sizeof buf);
        if (n < 0 && errno == EINTR) {
            continue;
        }
        if (n <= 0) {
            return text;
        }
        text.append(buf, (size_t)n);
    }
}

}  // namespace aos
