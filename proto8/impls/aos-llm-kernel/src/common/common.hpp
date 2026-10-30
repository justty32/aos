// common.hpp：【common】aos-llm-kernel 好幾個元素都用到的：型別別名、錯誤代號。
//
//   Json、Error   從 aos-util 拉進來的名字
//   code::*       信箱與信的代號在公開標頭 aos/llm_kernel.hpp（閘門也用），這裡直接沿用
#pragma once

#include "aos/llm_kernel.hpp"

namespace aos::llm_kernel {

using aos::Error;
using aos::Json;

}  // namespace aos::llm_kernel
