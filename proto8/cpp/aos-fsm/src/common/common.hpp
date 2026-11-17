// common.hpp：【common】aos-fsm 好幾個元素都用到的：型別別名、自己的錯誤代號。
//
//   Json、Error   從 aos-util 拉進來的名字
//   code::*       沿用 aos-loop 的（→ aos-exec → aos-util；StackMissing 也在那），再加 fsm 自己會吐的 StateUnknown、StateBad
#pragma once

#include "aos/loop.hpp"

namespace aos::fsm {

using aos::Error;
using aos::Json;

namespace code {
using namespace aos::loop::code;   // ArgumentsBad、FlagUnknown、StackMissing、CfgMissing、CfgBad、WriteFailed、EntryBad、LaunchFailed…
inline constexpr const char* StateUnknown = "StateUnknown";   // state 檔裡的狀態不在表上（10-22 起表壞一律 CfgBad）
inline constexpr const char* StateBad = "StateBad";           // state 檔在但讀不了（沒權限、是資料夾、不是 UTF-8）
}  // namespace code

}  // namespace aos::fsm
