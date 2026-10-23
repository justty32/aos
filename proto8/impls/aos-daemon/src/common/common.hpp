// common.hpp：【common】aos-daemon 好幾個元素都用到的：型別別名、錯誤代號。
//
//   Json、Error   從 aos-util 拉進來的名字
//   code::*       全沿用 aos-loop 的（→ aos-exec → aos-util）：FieldType、StackMissing、MkdirFailed、WriteFailed、LaunchFailed…
#pragma once

#include "aos/loop.hpp"

namespace aos::daemon {

using aos::Error;
using aos::Json;

namespace code {
using namespace aos::loop::code;
}  // namespace code

}  // namespace aos::daemon
