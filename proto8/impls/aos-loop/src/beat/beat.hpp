// beat.hpp：【beat】跑一拍（公開介面 block_signals、take_signal、run_beat 在 aos/loop.hpp）。內部標頭。
//
//   beat.cpp      run_beat：組好 `-- 目標 參數...` 交給 run_folder
//   folder.cpp    run_folder：fork 子行程、在裡面呼叫 aos-exec 的 run_cli（等同一支 aos-exec），
//                 等它結束、期間把訊號 kill 給它；量毫秒
//   signals.cpp   block_signals、take_signal；the_signals()＝那三個訊號
//
// 對應 Python 版 proto8/bin/aos_beat.py 的 run（`subprocess.Popen(["aos-exec", "--", x] + args)`）。
#pragma once

#include "common/common.hpp"

#include <signal.h>

#include <string>
#include <vector>

namespace aos::loop {

// SIGINT、SIGTERM、SIGHUP。
sigset_t the_signals();

// argv＝交給 aos-exec 的參數（不含程式名）。見 aos/loop.hpp 的 run_beat。
Beat run_folder(const std::vector<std::string>& argv);

}  // namespace aos::loop
