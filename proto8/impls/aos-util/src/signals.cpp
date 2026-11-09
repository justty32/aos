// signals.cpp：【aos-util】阻擋與取出收工訊號、保存舊遮罩並供子行程還原（說明見 include/aos/util/signals.hpp）。
#include "aos/util/signals.hpp"

#include <ctime>

namespace aos {

static sigset_t old_mask;
static bool mask_saved = false;

sigset_t the_signals() {
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGINT);
    sigaddset(&set, SIGTERM);
    sigaddset(&set, SIGHUP);
    return set;
}

void block_signals() {
    sigset_t set = the_signals();
    if (!mask_saved) {
        if (sigprocmask(SIG_BLOCK, &set, &old_mask) == 0) {
            mask_saved = true;
        }
    } else {
        sigprocmask(SIG_BLOCK, &set, nullptr);
    }
}

void block_more(const sigset_t& set) {
    sigprocmask(SIG_BLOCK, &set, nullptr);
}

void restore_signals() {
    if (mask_saved) {
        sigprocmask(SIG_SETMASK, &old_mask, nullptr);
    } else {
        sigset_t set = the_signals();
        sigprocmask(SIG_UNBLOCK, &set, nullptr);
    }
}

int take_signal() {
    sigset_t set = the_signals();
    timespec zero{0, 0};
    int sig = sigtimedwait(&set, nullptr, &zero);
    if (sig < 0) {
        return 0;
    }
    return sig;
}

}  // namespace aos
