// engine.hpp：【engine】反覆跑的程式的骨架 Loop（公開介面在 aos/loop.hpp）。內部標頭。
// 10-21 傍晚。
//
//   config.cpp   Loop 的建構子：讀設定檔（檔#/指標）、旗標蓋上、驗 exec／max／interval_ms／ctl／state、算兩扇窗的路徑、--enable-logs／--enable-counters、附加參數（add_args）；
//                parse_target、loop_cli
//   loop.cpp     serve／main_loop：每次讀 ctl → tend → 停不停 → 睡或跑一次（跑完印一行 log）→ 寫 state（有變才寫）；end、nap、signal_got、say
//   window.cpp   窗：read_ctl（N-06～N-08：壞的不採用、維持上一份好的、原因記 ctl_warning）、write_state、
//                write_window（先寫 .名字 再改名）、write_counter（選開的 counter_runs.txt）、proc_fields（pid、started_at_ticks、boot_id）、log_line（stdout 一行，11-02）
//   responded    記最近反應時間：處理新 ctl（含拒用壞指令）、收到信、起或收子項；state 帶 responded_at 並算進變動比較
#pragma once

#include "common/common.hpp"
