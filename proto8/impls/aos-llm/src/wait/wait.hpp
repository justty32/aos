// wait.hpp：【wait】收回信——在回信信箱裡找回某封信的那封、印 body.message、收掉；ask 的等待與撤信。
//
//   recv   回信信箱 BOX 的 new/ 裡找 letter.json 的 in_reply_to＝name 的回信（別人的不碰）：
//            沒到＝回 10（BOX 不是資料夾＝MailboxMissing）；到了＝認領（new → cur）→ deliver
//   ask_wait  每 20 毫秒看一次 <信箱>/reply/（中間收到 SIGINT／SIGTERM／SIGHUP 馬上醒）：回 id 的回信到了 → 認領 → deliver
//            原信在 new／cur／done 都沒有、也沒有回信＝LetterMissing（信被人刪了；照信走的方向 new → cur → done 依序看，不會看漏）
//            收到訊號＝撤信：new/<id> 改名回 tmp/ 再刪（改得成＝還沒被認領）；已經在 cur/（正在跑）就讓它跑完；
//            回信已經到了就收掉（沒到的，kernel 之後看寄信的人不在了會撤回）。回 128＋N
//            等多久不歸 aos-llm 管：kernel.json 的 timeout_ms、priority 的 deadline，或包它那格的 timeout_ms（10-15 KISS 1.8）
//   deliver（內部）  讀回信的 body：{"message": 物件, …}＝stdout 印一行 body.message、收掉（aos-post done：刪）、回 0；
//            {"error": {"code", "msg"}}＝收掉、丟 Error{那個代號}（main 印成 stderr 一行「aos-llm: 代號 原因」、退 1）；讀不懂＝收掉、ReplyBad
#pragma once

#include "common/common.hpp"

#include <string>

namespace aos::llm {

int recv(const std::string& box, const std::string& name);
int ask_wait(const Mailbox& mb, const std::string& id);

}  // namespace aos::llm
