#define _POSIX_C_SOURCE 200809L

#include "run_internal.hpp"

#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstring>

#include <time.h>

namespace aos::detail {
namespace {

volatile std::sig_atomic_t g_stop_requested = 0;
void request_stop(int) { g_stop_requested = 1; }

class LoopSignals {
public:
    bool install(int &error) {
        g_stop_requested = 0;
        struct sigaction action {};
        action.sa_handler = request_stop;
        sigemptyset(&action.sa_mask);
        action.sa_flags = SA_RESETHAND;
        if (sigaction(SIGINT, &action, &old_int_) != 0) {
            error = errno;
            return false;
        }
        int_installed_ = true;
        if (sigaction(SIGTERM, &action, &old_term_) != 0) {
            error = errno;
            return false;
        }
        term_installed_ = true;
        return true;
    }
    ~LoopSignals() {
        if (term_installed_) sigaction(SIGTERM, &old_term_, nullptr);
        if (int_installed_) sigaction(SIGINT, &old_int_, nullptr);
        g_stop_requested = 0;
    }

private:
    struct sigaction old_int_ {};
    struct sigaction old_term_ {};
    bool int_installed_ = false;
    bool term_installed_ = false;
};

void sleep_milliseconds(std::uint64_t interval) {
    constexpr std::uint64_t kMillisecondsPerSecond = 1000;
    constexpr std::uint64_t kNanosecondsPerMillisecond = 1000000;
    struct timespec delay {
        static_cast<time_t>(interval / kMillisecondsPerSecond),
        static_cast<long>((interval % kMillisecondsPerSecond) *
                          kNanosecondsPerMillisecond)
    };
    nanosleep(&delay, nullptr);
}

}  // namespace

int run_exec_loop(const char *folder, std::uint64_t interval) {
    LoopSignals signals;
    int error = 0;
    if (!signals.install(error)) {
        std::fprintf(stderr, "aos exec: cannot install signal handlers: %s\n",
                     std::strerror(error));
        return 1;
    }
    for (;;) {
        bool did_work = false;
        const int result = run_exec_once(folder, did_work);
        if (result == 3) return 3;
        if (g_stop_requested != 0) return 0;
        if (!did_work && interval != 0) {
            sleep_milliseconds(interval);
            if (g_stop_requested != 0) return 0;
        }
    }
}

}  // namespace aos::detail
