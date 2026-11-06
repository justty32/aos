// signals.cpp：【run】將訊號操作轉交 aos-util（說明見 aos/loop.hpp）。
//
// 為什麼整支程式的壽命都擋著：跑到一半收到 SIGTERM 時，loop 自己不能先死（那次會變孤兒、state 寫一半），
// 要先把訊號轉給那次、等它收完，再以 128＋N 結束（CONVENTION P-36「先收好自己起的子程式、寫好狀態再結束，結束碼非 0」）。
// 兩次之間收到的就排在 kernel 裡，下一次開跑前用 sigtimedwait（不等）取出來。
#include "run/run.hpp"

#include "aos/signals.hpp"

namespace aos::loop {

sigset_t the_signals() {
    return aos::the_signals();
}

void block_signals() {
    aos::block_signals();
}

int take_signal() {
    return aos::take_signal();
}

}  // namespace aos::loop
