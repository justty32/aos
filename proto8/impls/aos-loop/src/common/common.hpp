// common.hpp：【common】aos-loop 好幾個元素都用到的：型別別名。
//
//   Json、Error   從 aos-util 拉進來的名字
//   code::*、Beat 在公開標頭 aos/loop.hpp（程式裡一律寫 code::Xxx）
#pragma once

#include "aos/loop.hpp"

namespace aos::loop {

using aos::Error;
using aos::Json;

}  // namespace aos::loop
