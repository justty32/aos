// signals.cpp：【aos-util】收 SIGINT／SIGTERM／SIGHUP：擋住、用 signalfd 讀（說明見 include/aos/signals.hpp）。
#include "aos/signals.hpp"

#include <cerrno>

#include <poll.h>
#include <sys/signalfd.h>
#include <unistd.h>

namespace aos {

static sigset_t caught_signals() {
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGINT);
    sigaddset(&set, SIGTERM);
    sigaddset(&set, SIGHUP);
    return set;
}

void SignalCatcher::start() {
    sigset_t set = caught_signals();
    sigprocmask(SIG_BLOCK, &set, &old_);       // 擋住：收到的訊號在 kernel 裡排隊，不會打死我們
    fd_ = signalfd(-1, &set, SFD_CLOEXEC | SFD_NONBLOCK);
}

void SignalCatcher::drain() {
    signalfd_siginfo info;
    while (fd_ >= 0 && read(fd_, &info, sizeof info) == (ssize_t)sizeof info) {
        if (!first_) {
            first_ = (int)info.ssi_signo;
        }
    }
}

void SignalCatcher::sleep(int ms) {
    pollfd p{fd_, POLLIN, 0};   // fd_ 是 -1 時 poll 不看它，等於單純睡
    if (poll(&p, 1, ms) > 0) {
        drain();
    }
}

void SignalCatcher::stop() {
    if (fd_ < 0) {
        return;
    }
    drain();                                   // 還在排隊的先讀掉，不然一解開擋就照預設把我們打死
    close(fd_);
    fd_ = -1;
    sigprocmask(SIG_SETMASK, &old_, nullptr);
}

}  // namespace aos
