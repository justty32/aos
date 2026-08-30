#define _POSIX_C_SOURCE 200809L

#include <aos/exec.hpp>

#include "clock.hpp"
#include "spawn_prep.hpp"
#include "tempfile.hpp"
#include "wait.hpp"

#include <cerrno>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include <signal.h>
#include <sys/types.h>
#include <unistd.h>

namespace aos::exec {
namespace {

struct TempFds {
    int input = -1;
    int output = -1;
    int error = -1;
};

struct ChildPlan {
    int input_fd;
    int output_fd;
    int error_fd;
    const char *cwd;
    const char *executable;
    char *const *argv;
    char *const *envp;
    int failure_status;
};

void close_if_open(int fd) {
    if (fd >= 0) {
        close(fd);
    }
}

void close_all(const TempFds &fds) {
    close_if_open(fds.input);
    close_if_open(fds.output);
    close_if_open(fds.error);
}

std::string system_error(const std::string &action, int error) {
    return action + ": " + std::strerror(error);
}

bool prepare_temp_files(const Spawn &spawn, Running &item, TempFds &fds) {
    fds.input = detail::make_temp("stdin", item.stdin_path);
    if (fds.input < 0) {
        item.error = system_error("無法建立 stdin 暫存檔", errno);
        return false;
    }
    fds.output = detail::make_temp("stdout", item.stdout_path);
    if (fds.output < 0) {
        item.error = system_error("無法建立 stdout 暫存檔", errno);
        return false;
    }
    fds.error = detail::make_temp("stderr", item.stderr_path);
    if (fds.error < 0) {
        item.error = system_error("無法建立 stderr 暫存檔", errno);
        return false;
    }
    if (!detail::write_fully(fds.input, spawn.stdin_data.data(),
                             spawn.stdin_data.size())) {
        item.error = system_error("無法寫入 stdin 暫存檔", errno);
        return false;
    }
    if (lseek(fds.input, 0, SEEK_SET) < 0) {
        item.error = system_error("無法重設 stdin 暫存檔", errno);
        return false;
    }
    return true;
}

bool redirect_fd(int fd, int target) {
    if (dup2(fd, target) < 0) {
        return false;
    }
    if (fd != target) {
        close(fd);
    }
    return true;
}

[[noreturn]] void run_child(const ChildPlan &plan) {
    if (setpgid(0, 0) != 0 ||
        !redirect_fd(plan.input_fd, STDIN_FILENO) ||
        !redirect_fd(plan.output_fd, STDOUT_FILENO) ||
        !redirect_fd(plan.error_fd, STDERR_FILENO)) {
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

std::uint64_t deadline_after(std::uint64_t timeout_ms) {
    if (timeout_ms == 0) {
        return 0;
    }
    const std::uint64_t now = detail::monotonic_ms();
    if (timeout_ms > std::numeric_limits<std::uint64_t>::max() - now) {
        return std::numeric_limits<std::uint64_t>::max();
    }
    return now + timeout_ms;
}

}  // namespace

std::vector<Running> start_all(const std::vector<Spawn> &spawns) {
    std::vector<Running> running;
    running.reserve(spawns.size());

    for (const Spawn &spawn : spawns) {
        Running item;
        item.timeout_ms = spawn.timeout_ms;
        item.started_at = now_iso8601();

        TempFds fds;
        if (!prepare_temp_files(spawn, item, fds)) {
            close_all(fds);
            running.push_back(std::move(item));
            continue;
        }

        std::vector<char *> argv;
        argv.reserve(spawn.argv.size() + 1);
        for (const std::string &argument : spawn.argv) {
            argv.push_back(const_cast<char *>(argument.c_str()));
        }
        argv.push_back(nullptr);

        detail::SpawnPrep prep;
        detail::prepare_spawn(spawn, prep);
        const ChildPlan plan{
            fds.input,
            fds.output,
            fds.error,
            spawn.cwd.empty() ? nullptr : spawn.cwd.c_str(),
            prep.executable.c_str(),
            argv.data(),
            prep.envp.data(),
            prep.failure_status,
        };

        const pid_t pid = fork();
        if (pid == 0) {
            run_child(plan);
        }
        if (pid < 0) {
            item.error = system_error("fork 失敗", errno);
            close_all(fds);
            running.push_back(std::move(item));
            continue;
        }

        close_all(fds);
        if (setpgid(pid, pid) != 0 && errno != EACCES) {
            const int saved_error = errno;
            kill(pid, SIGKILL);
            int ignored_status = 0;
            detail::wait_retry(pid, &ignored_status, 0);
            item.error = system_error("setpgid 失敗", saved_error);
            running.push_back(std::move(item));
            continue;
        }

        item.pid = pid;
        item.deadline_mono_ms = deadline_after(spawn.timeout_ms);
        running.push_back(std::move(item));
    }
    return running;
}

}  // namespace aos::exec
