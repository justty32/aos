// send.hpp：【send】寄信——找 kernel 的信箱、讀請求信的 body、寄進 new/、撤信。
//
//   kernel     信箱＝$AOS_LLM_KERNEL/requests/（N-63 ②；值＝llm kernel 的 stack，11-05）；沒設、不是資料夾＝LlmKernelMissing
//              相對的：有 $AOS_DAEMON＝相對它、沒有＝相對 cwd（11-05）
//   read_body  stdin 讀整份 body（一份 JSON）：{"endpoint"?: 代號字串, "request": {"messages": [...], ...}, "priority"?}
//              ——呼叫端自己組（thinking 11-04 think-as-function 03 § 1 think 寫的 request.json 就是這個形狀）；
//              不是物件、沒有 request、request 不是物件、messages 不是陣列、endpoint 不是字串＝RequestBad；
//              priority（有給 --priority 就先蓋上）先驗（parse_priority；壞＝PriorityBad，不寄）
//   send       非同步寄（aos-llm send）：回信信箱 reply_to 沒有就建（aos-post 的 init）、kernel 信箱的 tmp／new 沒有就建，
//              交給 aos-post 的 send 寄（信封 sender／sent_at／reply_to 由它寫；預設名＝時間開頭）；**不建 sender.flock**
//              （kernel 看不到檔＝不判寄信人在不在、照跑；11-04 衝突 2 (a)）。回信件名稱
//   send_held  同步寄（aos-llm ask）：回信信箱＝<信箱>/reply/（沒有就建），信寫進 tmp/.<id>/（先建 sender.flock、flock 住，
//              拿到行程結束）再改名進 new/<id>——kernel 看這把鎖知道寄信的人還在（10-24，S15）。回信件名稱
//   regret     撤回還在 new/ 的信（aos-post 的 regret）；已被認領或沒有＝RegretFailed
#pragma once

#include "common/common.hpp"

#include <optional>
#include <string>

namespace aos::llm {

Mailbox kernel();

// 那台 llm kernel 不在跑的原因（英文一句；在跑＝空字串）。warn_idle 與 recv 共用（11-10 坑-102）。
std::string idle_reason(const Mailbox& mb);
void warn_idle(const Mailbox& mb, const std::string& why, const std::string& id);   // why 非空（那裡沒有在跑的 llm daemon）＝寄完 stderr 提醒一行、說信 id 寫到哪（不擋）
Json read_body(const std::optional<std::string>& priority);
std::string send(const Mailbox& mb, const Json& body, const std::string& reply_to);
std::string send_held(const Mailbox& mb, const Json& body);
void regret(const Mailbox& mb, const std::string& name);

}  // namespace aos::llm
