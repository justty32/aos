// aos/util/signals.hpp：【aos-util】建立、阻擋與取出收工訊號，並保留及還原阻擋前的遮罩。
//
// 開執行緒前呼叫 block_signals：訊號留在 kernel 排隊，由 take_signal 每次取出一個。
// the_signals 提供同一組訊號，讓呼叫者建立自己的等待機制。
#pragma once

#include <signal.h>

namespace aos {

// 整支程式壽命的遮罩：開執行緒前呼叫 block_signals；take_signal 不等待，沒有回 0。
sigset_t the_signals();
void block_signals();
// 額外阻擋一組訊號，不改 block_signals 第一次保存的舊遮罩。
void block_more(const sigset_t& set);
// fork 後、exec 前的子行程還原成 block_signals 之前的遮罩（含額外擋住的訊號）。
// 沒呼叫過 block_signals 就只解開三個收工訊號；只用 async-signal-safe 呼叫、不配置記憶體。
void restore_signals();
int take_signal();

}  // namespace aos
