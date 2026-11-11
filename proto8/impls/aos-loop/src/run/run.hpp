// run.hpp：【run】跑一次（公開介面 block_signals、take_signal、run_once 在 aos/loop.hpp）。內部標頭。
//
//   run.cpp      run_once：目標＝組好 `-- 目標 參數...` 交給 run_folder；單子＝交給 run_inline（10-24）
//   inline.cpp   run_inline：行程內 aos-exec 的 run_inst，跑的期間 AOS_CF／AOS_CD／AOS_CO 設成單子的位置
//   folder.cpp    run_folder：fork 子行程、在裡面呼叫 aos-exec 的 run_cli（等同一支 aos-exec），
//                 等它結束、期間把訊號 kill 給它；量毫秒
//   signals.cpp   block_signals、take_signal、the_signals 轉交 aos-util 的訊號介面
#pragma once

#include "common/common.hpp"

#include <signal.h>

#include <string>
#include <vector>

namespace aos::loop {

// SIGINT、SIGTERM、SIGHUP。
sigset_t the_signals();

// argv＝交給 aos-exec 的參數（不含程式名）。見 aos/loop.hpp 的 run_once。
// timeout_ms＞0（11-11 on_start／on_stop）：到時間 SIGTERM 給子行程、再 1 秒還在就 SIGKILL，timed_out＝true。
Run run_folder(const std::vector<std::string>& argv, long long timeout_ms = 0);

// t.inst 是單子（10-24）。見 aos/loop.hpp 的 run_once。
Run run_inline(const Target& t);

}  // namespace aos::loop
