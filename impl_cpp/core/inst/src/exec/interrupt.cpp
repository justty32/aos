// interrupt.cpp：已 fork 未收線的子行程登記表，interrupt_running 對它們的 process group 送訊號（async-signal-safe）（搬自 archive/aos-v1/core/exec，行為不改）。
#define _POSIX_C_SOURCE 200809L

#include <aos/exec.hpp>

#include "interrupt.hpp"

#include <array>
#include <atomic>

#include <signal.h>
#include <sys/types.h>

namespace aos::exec {
namespace {

constexpr std::size_t kRunningCapacity = 256;
static_assert(std::atomic<pid_t>::is_always_lock_free,
              "atomic pid_t must be lock-free to be used safely in a signal handler");
std::array<std::atomic<pid_t>, kRunningCapacity> running_pids{};

}  // namespace

namespace detail {

void register_running(pid_t pid) {
    for (auto &slot : running_pids) {
        pid_t empty = 0;
        if (slot.compare_exchange_strong(empty, pid,
                                         std::memory_order_release,
                                         std::memory_order_relaxed)) {
            return;
        }
    }
}

void unregister_running(pid_t pid) {
    for (auto &slot : running_pids) {
        pid_t expected = pid;
        if (slot.compare_exchange_strong(expected, 0,
                                         std::memory_order_acq_rel,
                                         std::memory_order_relaxed)) {
            return;
        }
    }
}

}  // namespace detail

int interrupt_running(int signal_number) {
    int sent = 0;
    for (auto &slot : running_pids) {
        const pid_t pid = slot.load(std::memory_order_acquire);
        if (pid > 0 && ::kill(-pid, signal_number) == 0) {
            ++sent;
        }
    }
    return sent;
}

}  // namespace aos::exec
