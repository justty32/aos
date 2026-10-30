// common.hpp：【common】aos-llm-send 好幾個元素都用到的：型別別名、錯誤代號（信箱與信的代號在 aos-llm-kernel 的 aos/llm_kernel.hpp）。
#pragma once

#include "aos/llm_kernel.hpp"

namespace aos::llm_send {

using aos::Error;
using aos::Json;
using aos::llm_kernel::Mailbox;

// 回信信箱：<kernel 的信箱>/reply/（N-16 信箱，tmp／new／cur；10-30 回信改走 reply_to）。
// 放在 kernel 的信箱底下、不放寄信人自己的 stack：kernel（可能是別的帳號、在沙箱外）要寫得進去，
// 而 kernel 的信箱本來就是兩邊都寫得到的地方（沙箱綁它、root/setup.sh 給它權限）；沙箱裡也不一定有 AOS_STACK。
inline std::string reply_box(const Mailbox& mb) { return mb.root + "/reply"; }
namespace code = aos::llm_kernel::code;

}  // namespace aos::llm_send
