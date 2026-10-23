// common.hpp：【common】aos-fsm 好幾個元素都用到的：型別別名、自己的錯誤代號。
//
//   Json、Error   從 aos-util 拉進來的名字
//   code::*       沿用 aos-loop 的（→ aos-exec → aos-util；StackMissing 也在那），再加 fsm 自己會吐的 StateUnknown
#pragma once

#include "aos/loop.hpp"

namespace aos::fsm {

using aos::Error;
using aos::Json;

namespace code {
using namespace aos::loop::code;   // Usage、StackMissing、ReadFailed、JsonSyntax、FieldType、WriteFailed、EntryBad、LaunchFailed…
inline constexpr const char* StateUnknown = "StateUnknown";   // state 檔裡的狀態不在表上（10-22 起表壞一律 FieldType）
}  // namespace code

}  // namespace aos::fsm
