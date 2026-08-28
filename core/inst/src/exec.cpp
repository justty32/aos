#define _POSIX_C_SOURCE 200809L

#include <aos/inst.hpp>

#include "spawn_prep.hpp"
#include "wait.hpp"

#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include <fcntl.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

namespace aos {
namespace {

constexpr std::uint64_t kTimeoutGraceMs = 2000;

int open_retry(const char *path, int flags, mode_t mode = 0) {
    int fd;
    do {
        fd = open(path, flags, mode);
    } while (fd < 0 && errno == EINTR);
    return fd;
}

bool write_fully(int fd, const char *data, std::size_t size) {
    while (size != 0) {
        ssize_t written;
        do {
            written = write(fd, data, size);
        } while (written < 0 && errno == EINTR);

        if (written <= 0) {
            return false;
        }
        data += written;
        size -= static_cast<std::size_t>(written);
    }
    return true;
}

// fsync 本身可能被訊號中斷（不像 close，重打 fsync 是安全的：fd 沒被回收）。
bool fsync_retry(int fd) {
    int rc;
    do {
        rc = fsync(fd);
    } while (rc != 0 && errno == EINTR);
    return rc == 0;
}

// 只 fsync 檔案本身救不了「新建檔的目錄項沒落盤」——崩潰後檔案可能整個不存在。
// `path` 沒有 '/' 時父目錄就是 cwd；`"/x"` 這種的父目錄是根。
bool fsync_parent_dir(const std::string &path) {
    const std::size_t slash = path.rfind('/');
    std::string parent = ".";
    if (slash == 0) {
        parent = "/";
    } else if (slash != std::string::npos) {
        parent = path.substr(0, slash);
    }
    const int fd = open_retry(parent.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) {
        return false;
    }
    const bool synced = fsync_retry(fd);
    const bool closed = close(fd) == 0;
    return synced && closed;
}

// fork 之後、execve 之前只能用 async-signal-safe 的操作，所以是 write(2) 而不是
// fprintf：不配置記憶體、不做字串串接、不碰 stdio 的鎖。
void write_safe(int fd, const char *data, std::size_t size) {
    while (size != 0) {
        const ssize_t written = write(fd, data, size);
        if (written <= 0) {
            if (written < 0 && errno == EINTR) continue;
            return;  // 寫不出去就算了：這裡沒有第二個管道可以求救
        }
        data += static_cast<std::size_t>(written);
        size -= static_cast<std::size_t>(written);
    }
}

// 重導向開檔失敗以前是全靜默的：子行程 _exit(126)、`aos exec` 零輸出，使用者看不
// 出原因。這裡在子行程裡直接寫一行 warning 到 fd 2。
//
// 順序上寫得出去：stdin／stdout 的重導向失敗時 fd 2 根本還沒被動；stderr 自己開檔
// 失敗時 dup2 也還沒發生——兩種情形 fd 2 都仍是父行程原本的 stderr。
// `path` 是 fork 之前就在記憶體裡的 C 字串，這裡只讀不動它；長度自己數，因為
// `strlen` 不在 POSIX 的 async-signal-safe 清單裡。
void warn_redirect_failed(const char *path) {
    static const char prefix[] =
        "aos exec: warning: cannot open redirect target: ";
    write_safe(STDERR_FILENO, prefix, sizeof(prefix) - 1);
    std::size_t length = 0;
    while (path[length] != '\0') ++length;
    write_safe(STDERR_FILENO, path, length);
    write_safe(STDERR_FILENO, "\n", 1);
}

bool write_exit_status(const std::string &path, int status) {
    char buffer[32];
    const int length = std::snprintf(buffer, sizeof(buffer), "%d\n", status);
    if (length < 0 || static_cast<std::size_t>(length) >= sizeof(buffer)) {
        return false;
    }

    // O_CLOEXEC：這是整個 core/inst 裡唯一活在「會 fork 的多執行緒行程」
    // （run_batch 的 parallel thread）裡的 open——別的 thread 正好 fork 的話，
    // 這個**可寫**的 fd 就跟著漏進 execve 之後的外部程式。
    const int fd =
        open_retry(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0666);
    if (fd < 0) {
        return false;
    }

    // exit 檔是崩潰後對帳的證據：內容與目錄項都落盤才算數（S7 fsync 掃尾）。
    const bool wrote = write_fully(fd, buffer, static_cast<std::size_t>(length));
    const bool synced = wrote && fsync_retry(fd);
    const bool closed = close(fd) == 0;
    if (!wrote || !synced || !closed) {
        return false;
    }
    return fsync_parent_dir(path);
}

// stdin/stdout/stderr 重導向：這裡只開檔、`dup2` 給子行程，不寫入內容——子行程
// 自己往這個 fd 寫什麼、寫多少，父行程管不到也不 fsync（S7 fsync 掃尾的已知豁免：
// child stream 檔不算「本層寫檔」）。
bool child_redirect(const char *path, int target_fd, int flags) {
    if (path == nullptr) {
        return true;
    }

    // O_CLOEXEC 加在這個「只當 dup2 來源」的 fd 上是安全的：dup2 產生的新描述子
    // 不帶 CLOEXEC，所以重導向本身照活，只有多餘的原 fd 被 execve 關掉。
    const int fd = open_retry(path, flags | O_CLOEXEC, 0666);
    if (fd < 0) {
        warn_redirect_failed(path);
        return false;
    }
    if (fd == target_fd) {
        // open 剛好拿到目標描述子（呼叫者事先把它關掉時會發生）。dup2(fd, fd) 是
        // no-op，**不會**清掉 CLOEXEC，得自己清，否則 execve 之後重導向就沒了。
        return fcntl(fd, F_SETFD, 0) == 0;
    }
    if (dup2(fd, target_fd) < 0) {
        close(fd);
        return false;
    }
    close(fd);
    return true;
}

struct ChildPlan {
    const char *stdin_path;
    const char *stdout_path;
    const char *stderr_path;
    bool stderr_merge;
    const char *cwd;
    const char *executable;
    char *const *argv;
    char *const *envp;
    int failure_status;
};

[[noreturn]] void run_child(const ChildPlan &plan) {
    if (!child_redirect(plan.stdin_path, STDIN_FILENO, O_RDONLY) ||
        !child_redirect(plan.stdout_path, STDOUT_FILENO,
                        O_WRONLY | O_CREAT | O_TRUNC) ||
        (!plan.stderr_merge &&
         !child_redirect(plan.stderr_path, STDERR_FILENO,
                         O_WRONLY | O_CREAT | O_TRUNC)) ||
        (plan.stderr_merge && dup2(STDOUT_FILENO, STDERR_FILENO) < 0)) {
        _exit(detail::kExitSetupFailed);
    }
    if (plan.cwd != nullptr && chdir(plan.cwd) != 0) {
        _exit(detail::kExitSetupFailed);
    }
    if (plan.failure_status != 0) {
        _exit(plan.failure_status);
    }

    execve(plan.executable, plan.argv, plan.envp);
    _exit(detail::kExitExecFailed);
}

}  // namespace

ExecState execute(inst_t &inst, ExecResult &result) {
    result = ExecResult{};

    if (inst.argv.empty() || inst.argv[0].empty()) {
        return ExecState::InvalidArgument;
    }

    std::vector<char *> argv;
    argv.reserve(inst.argv.size() + 1);
    for (std::string &arg : inst.argv) {
        argv.push_back(arg.data());
    }
    argv.push_back(nullptr);

    detail::SpawnPrep prep;
    detail::prepare_spawn(inst, prep);
    const auto path_or_null = [](const std::string &path) {
        return path.empty() ? nullptr : path.c_str();
    };
    const ChildPlan child_plan{
        path_or_null(inst.stdin_path), path_or_null(inst.stdout_path),
        path_or_null(inst.stderr_path), inst.stderr_merge,
        path_or_null(inst.cwd),
        prep.executable.c_str(), argv.data(), prep.envp.data(),
        prep.failure_status,
    };

    const pid_t pid = fork();
    if (pid < 0) {
        result.error = errno;
        return ExecState::SpawnFailed;
    }
    if (pid == 0) {
        if (setpgid(0, 0) != 0) {
            _exit(detail::kExitSetupFailed);
        }
        run_child(child_plan);
    }

    if (setpgid(pid, pid) != 0 && errno != EACCES) {
        const int saved_error = errno;
        kill(pid, SIGKILL);
        int ignored_status = 0;
        detail::wait_retry(pid, &ignored_status, 0);
        result.error = saved_error;
        return ExecState::SpawnFailed;
    }

    int raw_status = 0;
    pid_t waited = 0;
    if (inst.timeout_ms == 0) {
        waited = detail::wait_retry(pid, &raw_status, 0);
    } else {
        int wait_error = 0;
        if (detail::wait_until(pid, inst.timeout_ms, raw_status, wait_error)) {
            waited = pid;
        } else if (wait_error != 0) {
            result.error = wait_error;
            return ExecState::WaitFailed;
        } else {
            result.timed_out = true;
            kill(-pid, SIGTERM);
            if (detail::wait_until(pid, kTimeoutGraceMs, raw_status, wait_error)) {
                waited = pid;
                /*
                 * 領頭的子行程死了，不代表整個群組死了：忽略 SIGTERM 的孫行程
                 * 會活下來，而殺得掉孫行程正是這裡用行程群組的全部理由。收掉
                 * 領頭者之後補一發 SIGKILL 掃過剩下的成員 —— SIGKILL 擋不掉。
                 * 群組已經空了的話 kill 會回 ESRCH，那正是我們要的「無事發生」。
                 */
                kill(-pid, SIGKILL);
            } else if (wait_error != 0) {
                result.error = wait_error;
                return ExecState::WaitFailed;
            } else {
                kill(-pid, SIGKILL);
                waited = detail::wait_retry(pid, &raw_status, 0);
            }
        }
    }

    if (waited < 0) {
        result.error = errno;
        return ExecState::WaitFailed;
    }

    if (WIFSIGNALED(raw_status)) {
        result.status = 128 + WTERMSIG(raw_status);
        result.signalled = true;
    } else if (WIFEXITED(raw_status)) {
        result.status = WEXITSTATUS(raw_status);
    } else {
        return ExecState::WaitFailed;
    }

    if (!inst.exit_path.empty() &&
        !write_exit_status(inst.exit_path, result.status)) {
        return ExecState::ExitWriteFailed;
    }

    return ExecState::Ok;
}

const char *to_string(ExecState state) noexcept {
    switch (state) {
    case ExecState::Ok:
        return "Ok";
    case ExecState::InvalidArgument:
        return "InvalidArgument";
    case ExecState::SpawnFailed:
        return "SpawnFailed";
    case ExecState::WaitFailed:
        return "WaitFailed";
    case ExecState::ExitWriteFailed:
        return "ExitWriteFailed";
    }
    return "Unknown";
}

}  // namespace aos
