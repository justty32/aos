// aos/util/signals.hpp：【aos-util】建立、阻擋與非阻塞取出 SIGINT／SIGTERM／SIGHUP。
//
// 開執行緒前呼叫 block_signals：訊號留在 kernel 排隊，由 take_signal 每次取出一個。
// the_signals 提供同一組訊號，讓呼叫者建立自己的等待機制。
#pragma once

#include <signal.h>

namespace aos {

// 整支程式壽命的遮罩：開執行緒前呼叫 block_signals；take_signal 不等待，沒有回 0。
sigset_t the_signals();
void block_signals();
int take_signal();

}  // namespace aos
