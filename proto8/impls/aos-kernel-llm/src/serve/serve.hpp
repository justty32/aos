// serve.hpp：【serve】kernel 跑一次——讀設定、鎖信箱、收拾、排隊、認領、跑、回信。
//
//   read_cfg   kernel.json（`檔` 或 `檔#/指標`）：mailbox（信箱資料夾；相對的從 $AOS_STACK 算〔N-14 窗落在 $AOS_STACK 底下〕；
//              沒寫＝"mailbox"）、slots（同時跑幾封，正整數；沒寫＝1）、budget（額度，budget.hpp）、accept（只收哪幾張單子，見下）；其他 key 忽略（_entry…）。mailbox、slots、budget、accept 的指示詞先解
//              （aos-loop 的 resolve_keys）。壞了 CfgMissing／CfgBad／DirectiveBad
//   serve      跑一次（給 aos-loop／aos-daemon 一次次拍），回結束碼（0；跑的期間收到訊號＝收完 128＋N）：
//                1. 建信箱四格（tmp／new／cur／done）、flock 住 .flock（鎖不到＝LockFailed；10-29 原叫 .lock）；queue.json 的 counter_runs＋1
//                2. cur/ 裡還有信＝上一次 kernel 跑到一半死了：有 reply.json 就照它；跑信的子行程（cur/<id>/runner.json）還活著＝讓它跑完、
//                   這次少一格；都不是＝回 RunFailed（10-15 六題 6「回錯」，不重跑）；有回信的搬 done/
//                3. 收拾：tmp/、done/ 裡寄信的人不在了（sender.lock 沒人鎖）的刪掉；new/ 裡寄信的人不在了的先改名回 tmp/ 再刪（不白跑）；
//                   tmp/ 裡 . 開頭的＝閘門正在寫，有 letter.json 而沒人鎖才刪
//                4. 看 new/：letter.json 讀不懂、priority 壞＝回 LetterBad；有 accept 而單子不在名單裡＝回 InstUnknown；deadline 已過＝回 DeadlineMissed（都不佔格）
//                5. 排隊（queue.hpp 的 order），取前 slots 封：這一窗額度到頂（budget.hpp 的 spent）＝spent "refuse" 時剩下的全回 BudgetMissing、
//                   "wait" 時留在 new/ 等下一窗；沒到頂就認領（new → cur 改名；改不成＝閘門剛撤信，換下一封）、
//                   每封 fork 一個子行程跑（run_runner），全部跑完才往下（一次裡不補位）
//                6. 每封寫一行 $AOS_STACK/served.jsonl（含腦回報的 counter_tokens）、跑過的記進 used.json、cur → done；寫 queue.json
//   run_runner 子行程裡：環境換成信裡的 env（再加 AOS_KERNEL_REPORT＝cur/<id>/report.json，腦願意就把 usage 寫進去）、單子沒寫 stdout／stderr＝寫進信的 stdout.txt／stderr.txt、沒寫 stdin＝/dev/null，
//              有 accept 時環境不整份換：用 kernel 自己的，只疊上信裡 AOS_ 開頭的（寄信的改不了 PATH、LD_PRELOAD、PYTHONPATH；key 用 kernel 這邊的）
//   accept     10-24 堵沙箱信箱後門：[{"argv": [...], "cwd": "..."}]（cwd 相對的從 kernel.json 的資料夾算）；信裡單子的 argv 與 cwd 要跟其中一張一字不差，
//              而且不能自帶 envs、stdin、stdout、stderr、stdout_append、stderr_append。沒寫＝什麼都收（照舊）
//              先寫 cur/<id>/runner.json（自己的 pid＋started_at_ticks），交給 aos-exec 的 run_inst（timeout_ms、grace_ms、整群收都在裡面），結果寫 reply.json
#pragma once

#include "budget/budget.hpp"
#include "common/common.hpp"

#include <optional>
#include <string>
#include <vector>

namespace aos::kernel_llm {

struct Accepted {
    std::vector<std::string> argv;
    std::string cwd;   // 絕對路徑
};

struct Cfg {
    std::string mailbox;   // 絕對或從 cwd 算的路徑（已接上 $AOS_STACK）
    long long slots = 1;
    Budget budget;
    std::optional<std::vector<Accepted>> accept;   // 沒寫＝什麼都收
};

Cfg read_cfg(const std::string& spec, const std::string& stack);
int serve(const Cfg& cfg, const std::string& stack);

}  // namespace aos::kernel_llm
