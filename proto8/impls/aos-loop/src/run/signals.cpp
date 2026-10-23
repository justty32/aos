// signals.cpp：【run】擋訊號、兩次之間取訊號（說明見 aos/loop.hpp）。
//
// 為什麼整支程式的壽命都擋著：跑到一半收到 SIGTERM 時，loop 自己不能先死（那次會變孤兒、state 寫一半），
// 要先把訊號轉給那次、等它收完，再以 128＋N 結束（CONVENTION P-36「先收好自己起的子程式、寫好狀態再結束，結束碼非 0」）。
// 兩次之間收到的就排在 kernel 裡，下一次開跑前用 sigtimedwait（不等）取出來。
#include "run/run.hpp"

#include <ctime>

namespace aos::loop {

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

}  // namespace aos::loop
