// wait.hpp：【wait】等回信——輪詢 done/<id>、收到訊號撤信、把結果原樣交回。
//
//   wait_reply  每 20 毫秒看一次（中間收到 SIGINT／SIGTERM／SIGHUP 馬上醒）：
//                 done/<id> 在＝回信到了 → relay
//                 new／cur／done 都沒有＝LetterMissing（信被人刪了；照信走的方向 new → cur → done 依序看，不會看漏）
//                 收到訊號＝撤信：new/<id> 改名回 tmp/ 再刪（改得成＝還沒被認領）；已經在 cur/（正在跑）就讓它跑完，
//                 回信由 kernel 之後清掉（寄信的人不在了）；已經在 done/ 就直接刪。回 128＋N
//               等多久不歸閘門管：由包它那格的 timeout_ms 守（10-15 KISS 1.8）
//   relay       stdout.txt 原樣寫到自己的 stdout、stderr.txt 寫到自己的 stderr、刪掉 done/<id>；
//               回信是 {"code", "signal"}＝回那個碼（被訊號停掉的單子是 128＋N）；
//               回信是 {"error": {"code", "msg"}}（kernel 沒跑或跑不起來）＝丟 Error{那個代號}，main 印成自己的一行、退 1；
//               回信讀不懂＝ReplyBad
#pragma once

#include "common/common.hpp"

#include <string>

namespace aos::gate {

int wait_reply(const Mailbox& mb, const std::string& id);

}  // namespace aos::gate
