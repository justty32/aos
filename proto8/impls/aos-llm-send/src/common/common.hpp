// common.hpp：【common】aos-llm-send 好幾個元素都用到的：型別別名、錯誤代號（信箱與信的代號在 aos-llm-kernel 的 aos/llm_kernel.hpp）。
#pragma once

#include "aos/llm_kernel.hpp"

namespace aos::llm_send {

using aos::Error;
using aos::Json;
using aos::llm_kernel::Mailbox;
namespace code = aos::llm_kernel::code;

}  // namespace aos::llm_send
