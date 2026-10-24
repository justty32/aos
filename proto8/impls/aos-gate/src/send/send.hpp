// send.hpp：【send】寄信——找信箱、讀單子、寫成一封信丟進 new/。
//
//   mailbox   信箱＝$AOS_KERNEL（呼叫方在叫閘門的那一行綁，像 AOS_BRAIN_*，P-39）；沒設、不是資料夾＝MailboxMissing
//   post      spec＝單子檔（`檔` 或 `檔#/指標`）：
//               1. AOS_CF／AOS_CD／AOS_CO 設成單子的位置（同 aos-exec 跑 `檔#/指標` 的單子，10-24 代定 1）
//               2. load_cfg 讀、解整份指示詞（在閘門的環境解＝呼叫方那一刻的值；$ref 從單子檔的資料夾算）；不是物件＝CfgBad
//               3. priority 先驗（壞＝PriorityBad，不寄）
//               4. cwd 轉成絕對路徑（沒寫＝單子檔的資料夾，同 aos-exec；相對的接在它後面）——kernel 在別的資料夾跑也一樣
//               5. 信＝{"inst": 單子, "env": 這一刻閘門的整份環境, "priority": 原樣}；寫進 tmp/.<id>/（先建 sender.lock、flock 住，拿到行程結束）
//                  再改名進 new/<id>
//             回信號 id。
#pragma once

#include "common/common.hpp"

#include <string>

namespace aos::gate {

Mailbox mailbox();
std::string post(const Mailbox& mb, const std::string& spec);

}  // namespace aos::gate
