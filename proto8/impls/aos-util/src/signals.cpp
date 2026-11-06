// signals.cpp：【aos-util】建立訊號集合、阻擋與非阻塞取出 SIGINT／SIGTERM／SIGHUP（說明見 include/aos/util/signals.hpp）。
#include "aos/util/signals.hpp"

#include <ctime>

namespace aos {

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
    sigprocmask(SIG_BLOCK, &set, nullptr);
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
