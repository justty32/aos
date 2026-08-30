#define _POSIX_C_SOURCE 200809L

#include <aos/exec.hpp>

#include "clock.hpp"
#include "interrupt.hpp"
#include "tempfile.hpp"
#include "wait.hpp"

#include <cerrno>
#include <cstddef>
#include <cstring>
#include <string>
#include <vector>

#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>

namespace aos::exec {
namespace {

constexpr std::uint64_t kMaxPollMs = 50;

void append_error(std::string &error, const std::string &message) {
    if (!error.empty()) {
        error += "; ";
    }
    error += message;
}

void record_wait_error(Result &result, int error) {
    append_error(result.error, std::string("waitpid 失敗: ") + std::strerror(error));
}

void decode_status(int raw_status, Result &result) {
    if (WIFEXITED(raw_status)) {
        result.exit = WEXITSTATUS(raw_status);
        result.signal = 0;
    } else if (WIFSIGNALED(raw_status)) {
        result.exit = 0;
        result.signal = WTERMSIG(raw_status);
    } else {
        append_error(result.error, "waitpid 回傳了無法解讀的狀態");
    }
}

void collect_files(Running &item, Result &result) {
    detail::unlink_file(item.stdin_path, result.error);
    detail::read_file_and_unlink(item.stdout_path, result.stdout_text,
                                 result.error);
    detail::read_file_and_unlink(item.stderr_path, result.stderr_text,
                                 result.error);
    item.stdin_path.clear();
    item.stdout_path.clear();
    item.stderr_path.clear();
}

}  // namespace

std::vector<Result> wait_all(std::vector<Running> &running) {
    std::vector<Result> results(running.size());
    std::vector<int> raw_status(running.size(), 0);
    std::vector<bool> completed(running.size(), false);
    std::size_t remaining = 0;

    for (std::size_t index = 0; index < running.size(); ++index) {
        results[index].pid = running[index].pid;
        results[index].started_at = running[index].started_at;
        results[index].error = running[index].error;
        if (running[index].pid < 0 || !running[index].error.empty()) {
            completed[index] = true;
        } else {
            ++remaining;
        }
    }

    std::uint64_t poll_ms = 1;
    while (remaining != 0) {
        bool made_progress = false;
        const std::uint64_t now = detail::monotonic_ms();

        for (std::size_t index = 0; index < running.size(); ++index) {
            if (completed[index]) {
                continue;
            }

            const pid_t pid = running[index].pid;
            const pid_t waited = detail::wait_retry(pid, &raw_status[index], WNOHANG);
            if (waited == pid) {
                detail::unregister_running(pid);
                results[index].ended_at = now_iso8601();
                completed[index] = true;
                --remaining;
                made_progress = true;
                continue;
            }
            if (waited < 0) {
                detail::unregister_running(pid);
                record_wait_error(results[index], errno);
                results[index].ended_at = now_iso8601();
                completed[index] = true;
                --remaining;
                made_progress = true;
                continue;
            }

            const std::uint64_t deadline = running[index].deadline_mono_ms;
            if (deadline != 0 && now >= deadline) {
                kill(-pid, SIGKILL);
                const pid_t killed = detail::wait_retry(pid, &raw_status[index], 0);
                detail::unregister_running(pid);
                if (killed < 0) {
                    record_wait_error(results[index], errno);
                }
                results[index].ended_at = now_iso8601();
                completed[index] = true;
                --remaining;
                made_progress = true;
            }
        }

        if (remaining != 0) {
            detail::sleep_ms(poll_ms);
            poll_ms = made_progress ? 1
                                    : (poll_ms < kMaxPollMs / 2 ? poll_ms * 2
                                                                : kMaxPollMs);
        }
    }

    for (std::size_t index = 0; index < running.size(); ++index) {
        if (running[index].pid >= 0 && results[index].error.empty()) {
            decode_status(raw_status[index], results[index]);
        }
        collect_files(running[index], results[index]);
        if (results[index].ended_at.empty()) {
            results[index].ended_at = now_iso8601();
        }
    }
    return results;
}

}  // namespace aos::exec
