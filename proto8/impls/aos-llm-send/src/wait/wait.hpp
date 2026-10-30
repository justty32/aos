// wait.hpp：【wait】等回信——看回信信箱（<信箱>/reply/）裡有沒有回這封的信、收到訊號撤信、把結果原樣交回。
//
//   wait_reply  每 20 毫秒看一次（中間收到 SIGINT／SIGTERM／SIGHUP 馬上醒）：
//                 回信信箱 new/ 裡 letter.json 的 in_reply_to＝自己的信號＝回信到了 → 認領（new → cur）→ relay
//                 （回信是 N-16 的信，kernel 照信封的 reply_to 寄來；10-30 起不再去 done/<id> 撈，done/ 是 kernel 的紀錄）
//                 原信在 new／cur／done 都沒有、也沒有回信＝LetterMissing（信被人刪了；照信走的方向 new → cur → done 依序看，不會看漏）
//                 收到訊號＝撤信：new/<id> 改名回 tmp/ 再刪（改得成＝還沒被認領）；已經在 cur/（正在跑）就讓它跑完；
//                 回信已經到了就收掉（沒到的，kernel 之後看寄信的人不在了會撤回）。回 128＋N
//               等多久不歸閘門管：由包它那格的 timeout_ms 守（10-15 KISS 1.8）
//   relay       回信裡的 stdout.txt 原樣寫到自己的 stdout、stderr.txt 寫到自己的 stderr、收掉回信（aos-post finish：刪）；
//               body 是 {"code", "signal"}＝回那個碼（被訊號停掉的單子是 128＋N）；
//               body 是 {"error": {"code", "msg"}}（kernel 沒跑或跑不起來）＝丟 Error{那個代號}，main 印成自己的一行、退 1；
//               body 讀不懂＝ReplyBad
#pragma once

#include "common/common.hpp"

#include <string>

namespace aos::llm_send {

int wait_reply(const Mailbox& mb, const std::string& id);

}  // namespace aos::llm_send
