// serve.hpp：【serve】kernel 跑一次——讀設定、鎖信箱、收拾、排隊、認領、跑、回信。
//
//   read_cfg   kernel.json（`檔` 或 `檔#/指標`）：mailbox（信箱資料夾；相對的從 $AOS_STACK 算〔N-14 窗落在 $AOS_STACK 底下〕；
//              沒寫＝"mailbox"）、slots（同時跑幾封，正整數；沒寫＝1）；其他 key 忽略（_entry…）。mailbox、slots 的指示詞先解
//              （aos-loop 的 resolve_keys）。壞了 CfgMissing／CfgBad／DirectiveBad
//   serve      跑一次（給 aos-loop／aos-daemon 一次次拍），回結束碼（0；跑的期間收到訊號＝收完 128＋N）：
//                1. 建信箱四格（tmp／new／cur／done）、flock 住 .lock（鎖不到＝LockFailed）；queue.json 的 runs＋1
//                2. cur/ 裡還有信＝上一次 kernel 跑到一半死了：有 reply.json 就照它；跑信的子行程（cur/<id>/runner.json）還活著＝讓它跑完、
//                   這次少一格；都不是＝回 RunFailed（10-15 六題 6「回錯」，不重跑）；有回信的搬 done/
//                3. 收拾：tmp/、done/ 裡寄信的人不在了的刪掉；new/ 裡寄信的人不在了的先改名回 tmp/ 再刪（不白跑）
//                4. 看 new/：letter.json 讀不懂、priority 壞＝回 LetterBad；deadline 已過＝回 DeadlineMissed（都不佔格）
//                5. 排隊（queue.hpp 的 order），取前 slots 封：認領（new → cur 改名；改不成＝閘門剛撤信，換下一封）、
//                   每封 fork 一個子行程跑（run_runner），全部跑完才往下（一次裡不補位）
//                6. 每封寫一行 $AOS_STACK/served.jsonl、cur → done；寫 queue.json
//   run_runner 子行程裡：環境換成信裡的 env、單子沒寫 stdout／stderr＝寫進信的 stdout.txt／stderr.txt、沒寫 stdin＝/dev/null，
//              先寫 cur/<id>/runner.json（自己的 pid＋started_at_ticks），交給 aos-exec 的 run_inst（timeout_ms、grace_ms、整群收都在裡面），結果寫 reply.json
#pragma once

#include "common/common.hpp"

#include <string>

namespace aos::kernel_llm {

struct Cfg {
    std::string mailbox;   // 絕對或從 cwd 算的路徑（已接上 $AOS_STACK）
    long long slots = 1;
};

Cfg read_cfg(const std::string& spec, const std::string& stack);
int serve(const Cfg& cfg, const std::string& stack);

}  // namespace aos::kernel_llm
