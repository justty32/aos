// common.hpp：【common】aos-llm 好幾個元素都用到的：型別別名、錯誤代號（信箱型別用 aos-post、LLM 信件協定用 aos-llm-kernel）。
#pragma once

#include "aos/llm_kernel.hpp"
#include "aos/post.hpp"

namespace aos::llm {

using aos::Error;
using aos::Json;
using aos::post::Mailbox;

// ask 的回信信箱：<kernel 的信箱>/reply/（N-16 信箱，tmp／new／cur；10-30 回信改走 reply_to）。
// 放在 kernel 的信箱底下、不放寄信人自己的 stack：kernel（可能是別的帳號、在沙箱外）要寫得進去，
// 而 kernel 的信箱本來就是兩邊都寫得到的地方（沙箱綁它、root/setup.sh 給它權限）；沙箱裡也不一定有 AOS_STACK。
inline std::string reply_box(const Mailbox& mb) { return mb.root + "/reply"; }

namespace code {
using namespace aos::llm_kernel::code;
inline constexpr const char* LlmKernelMissing = "LlmKernelMissing";   // AOS_LLM_KERNEL 沒設、空的或不是資料夾
inline constexpr const char* EndpointsMissing = "EndpointsMissing";   // ls：kernel 的窗 endpoints.json 不在或讀不懂
using aos::post::code::RegretFailed;   // regret：信不在 new/（已被 kernel 認領，或本來就沒有）
}  // namespace code

}  // namespace aos::llm
