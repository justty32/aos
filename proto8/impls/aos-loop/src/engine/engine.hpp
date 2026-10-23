// engine.hpp：【engine】反覆跑的程式的骨架 Loop（公開介面在 aos/loop.hpp）。內部標頭。
// 照 proto8/bin/aos_loop.py（Loop、cli）與 aos_window.py（Ctl、write、beat），10-21 傍晚。
//
//   config.cpp   Loop 的建構子：讀設定檔（檔#/指標）、旗標蓋上、驗 val／max／interval_ms／ctl／state、算兩扇窗的路徑；
//                parse_target、loop_cli
//   loop.cpp     serve／main_loop：每拍讀 ctl → tend → 停不停 → 睡或跑一拍 → 寫 state；end、nap、signal_got、say
//   window.cpp   窗：read_ctl（N-06～N-08：壞的不採用、維持上一份好的、原因記 ctl_warning）、write_state、
//                write_window（先寫 .名字 再改名）、heartbeat（pid、started_at_ticks、boot_id、at）
#pragma once

#include "common/common.hpp"

namespace aos::loop {

// JSON 非負整數（true／false、小數不算）。
bool is_nat(const Json& v);

}  // namespace aos::loop
