// common.hpp：【common】aos-daemon 好幾個元素都用到的：型別別名、錯誤代號。
//
//   Json、Error   從 aos-util 拉進來的名字
//   code::*       全沿用 aos-loop 的（→ aos-exec → aos-util）：CfgBad、StackMissing、MkdirFailed、WriteFailed、LaunchFailed…
#pragma once

#include "aos/loop.hpp"

namespace aos::daemon {

using aos::Error;
using aos::Json;

namespace code {
using namespace aos::loop::code;
// 11-05（portable-flow 步 5「沒有才起、有就沿用」）：這個 stack 的 state.json 記的 daemon（pid＋started_at_ticks＋boot_id）還活著＝不起第二個
inline constexpr const char* DaemonRunning = "DaemonRunning";
// 11-05（feat-proto 件 5）：子行程照 limits 做 setrlimit／換身分失敗（小格 stderr.txt 一行、子行程退 1；見 child/limits.hpp）
inline constexpr const char* LimitBad = "LimitBad";
}  // namespace code

}  // namespace aos::daemon
