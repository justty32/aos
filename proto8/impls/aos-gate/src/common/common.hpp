// common.hpp：【common】aos-gate 好幾個元素都用到的：型別別名、錯誤代號（信箱與信的代號在 aos-kernel-llm 的 aos/kernel_llm.hpp）。
#pragma once

#include "aos/kernel_llm.hpp"

namespace aos::gate {

using aos::Error;
using aos::Json;
using aos::kernel_llm::Mailbox;
namespace code = aos::kernel_llm::code;

}  // namespace aos::gate
