// serve.hpp：【serve】kernel 跑一次——讀設定、鎖信箱、收拾、排隊、認領、跑 endpoint 函數、回信。
//
//   read_cfg   kernel.json（`檔` 或 `檔#/指標`；thinking 11-04 think-as-function 02 § 3）：
//                mailbox（信箱資料夾；相對的從 $AOS_STACK 算〔N-14 窗落在 $AOS_STACK 底下〕；沒寫＝"mailbox"）、
//                slots（同時跑幾封，正整數；沒寫＝1）、budget（額度，budget.hpp）、
//                exec（必填：預設的 endpoint 函數＝aos-exec 目標，資料夾、檔、`檔#/指標`；相對的從 kernel 定義資料夾〔kernel.json 所在〕算、轉成絕對）、
//                endpoints（必填、非空物件：代號 → 一組 llm 設定；一組裡 kernel 只認 exec〔選填，這組改用別的 endpoint 函數，相對的同上〕，
//                  其他鍵整個原樣交給 endpoint 函數）、endpoint（選填：預設代號，要在表裡）、timeout_ms（選填：跑 exec 的上限，非負整數）；
//                其他 key 忽略（_entry…；11-04 起 accept 拿掉＝不認、寫了也不管）。
//              指示詞：mailbox、slots、budget、exec、endpoint、timeout_ms 整格先解（aos-loop 的 resolve_keys）；endpoints 只換一層
//              （整張表可以 {"$ref": "endpoints.json#/"}），裡面每組到用的時候才解（解不開＝那封信回 DirectiveBad，kernel 照跑別封）。
//              壞了 CfgMissing／CfgBad／DirectiveBad
//   serve      跑一次（給 aos-loop／aos-daemon 一次次拍），回結束碼（0；跑的期間收到訊號＝收完 128＋N）：
//                1. 建信箱三格（tmp／new／cur）、flock 住 .flock（鎖不到＝LockFailed）；queue.json 的 counter_runs＋1
//                2. cur/ 裡還有信＝上一次 kernel 跑到一半死了：有 reply.json（讀得懂）就照它；跑信的子行程（cur/<id>/runner.json）還活著＝讓它跑完、
//                   這次少一格；都不是＝回 RunFailed（10-15 六題 6「回錯」，不重跑）；有回信的寄回信、刪掉
//                3. 收拾（只看有 sender.flock 的信；沒有＝非同步寄的，不判存活）：tmp/ 裡寄信的人不在了（沒人鎖）的刪掉；
//                   new/ 裡寄信的人不在了的先改名回 tmp/ 再刪（不白跑）；舊 kernel 留下的 done/ 整個刪
//                4. 看 new/：letter.json 讀不懂、body 不是物件、沒有 body.request（含頂層 inst／env 的舊閘門信）、endpoint 不是字串、priority 壞＝回 LetterBad；
//                   request 不是物件、messages 不是陣列、stream 真＝RequestBad；代號：沒寫又沒預設＝EndpointMissing、表裡沒有＝EndpointUnknown；
//                   那組解指示詞失敗＝DirectiveBad、不是物件或 exec 不是非空字串＝CfgBad；deadline 已過＝DeadlineMissed（都不佔格）
//                5. 排隊（queue.hpp 的 order），取前 slots 封：這一窗額度到頂（budget.hpp 的 spent）＝spent "refuse" 時剩下的全回 BudgetMissing、
//                   "wait" 時留在 new/ 等下一窗；沒到頂就認領（new → cur 改名；改不成＝寄信的剛撤信，換下一封）、
//                   每封 fork 一個子行程跑（run_runner），全部跑完才往下（一次裡不補位）
//                6. 每封寄回信（寄信的 sender.flock 已沒人鎖＝馬上撤回）、寫一行 $AOS_STACK/served.jsonl（含 endpoint、model、counter_tokens）、
//                   跑過的記進 used.json、整封刪掉（cur/<id>/；11-04 夜「舊信根本不用留，就是刪」）；寫 queue.json
//   start_runner  先在信的資料夾寫 request.json＝{"endpoint": 那組（指示詞已解、去掉 exec）, "request": body.request}，再 fork 子行程：
//              寫 cur/<id>/runner.json（自己的 pid＋started_at_ticks），交給 aos-exec 的 run_inst 跑
//              {"argv": ["aos-exec", "--stack", "<信>/", exec], "cwd": "<信>", "stdin": request.json, "stdout": reply.json, "stderr": stderr.txt, "timeout_ms"}
//              ——環境是 kernel 自己的（不換、不加 AOS_KERNEL_REPORT），stack＝這封信的資料夾（函數的小格，P-17）。跑完：
//              退非 0（含逾時、被訊號停）＝reply.json 換成 {"error": EndpointFailed, msg＝退幾號＋stderr.txt 第一行}；
//              退 0 而 reply.json 讀不懂（不是 {"message": 物件, …}，或是 error 形狀以外的）＝ReplyBad；讀得懂＝原樣當回信
#pragma once

#include "budget/budget.hpp"
#include "common/common.hpp"

#include <map>
#include <optional>
#include <string>
#include <vector>

namespace aos::llm_kernel {

struct Cfg {
    std::string mailbox;   // 絕對或從 cwd 算的路徑（已接上 $AOS_STACK）
    long long slots = 1;
    Budget budget;
    std::string exec;                                   // 預設的 endpoint 函數（絕對路徑，可帶 #/指標）
    Json endpoints = Json::object();                    // 代號 → 一組（只換過表這一層，每組裡的指示詞還沒解）
    std::map<std::string, std::string> endpoint_dirs;   // 代號 → 那組裡相對 $ref 的起點
    std::optional<std::string> endpoint;                // 預設代號
    std::optional<long long> timeout_ms;
    std::string base;                                   // kernel 定義資料夾（相對的 exec 從這裡算）
};

Cfg read_cfg(const std::string& spec, const std::string& stack);
int serve(const Cfg& cfg, const std::string& stack);

}  // namespace aos::llm_kernel
