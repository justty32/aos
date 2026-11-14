# kernel 與額度

← [README](README.md)

llm kernel（lib/aos/kernel_llm）、腦額度、找 kernel、kernel_gate 的意見。

## BudgetMissing 只給一行文字，agent 不知道何時能重試

- 主題：kernel 與額度
- 哪裡：llm kernel 對超額請求回的 `{"error": {"code": "BudgetMissing", "msg": ...}}`（`lib/aos/kernel_llm/llm_rules.py`）；agent-fsm `wait.py` 的 BudgetMissing 分支。
- 現象：錯誤只有一行英文，例如 `budget.senders key "..." (sender ...): max_calls 150 reached in this window (day); not run`。agent 讀不到「窗口何時結束」「是不是 `window: "all"`、永不重置」。AK17 只好用固定冷卻（30 秒起加倍、30 分鐘封頂）盲目重寄：day 窗口可能白敲幾小時，all 窗口會每 30 分鐘敲一次、永遠敲下去。Argon 審 AK17 時也提過（A1），當時要解析 msg 才做得到，所以放棄。
- 建議：error 物件多帶結構化欄位，例如 `"window": "day"`、`"resets_at": "<ISO 時間>"`（all 給 null）、`"key": "<sender key>"`。wait.py 把冷卻的 until 設成 resets_at；null 就只通知不重試，或拉長間隔。
- 痛的程度：拖慢
- 提出者與日期：ok-astra 2026-11-14
- 出處：wf/temp/ok-astra/aos-advice/budget-refusal-structured-retry.md；proto8/thinking/2026-11/14/astra-kernel-1114.md AK17 節；commit 2368ee3af
- 狀態：已解（ok-astra，313ce20ec）。kernel 的 BudgetMissing 多帶 `scope`、`window`、`since`、`resets_at`（all 為 null）、`limit`、`max`、`endpoint`／`key`；agent-fsm 冷卻等到 `resets_at`＋5 秒，`window all` 寄 BLOCKED 後停下（退 1、不記冷卻）；舊 kernel 照 AK17（2368ee3af）的冷卻。換樹清單見 astra-kernel-1114 ADV 節，等換樹才在活樹生效。

## aos-llm ls 沒設 AOS_LLM_KERNEL 就不能用

- 主題：kernel 與額度
- 哪裡：`aos-llm ls`。
- 現象：`aos-llm: error: LlmKernelMissing AOS_LLM_KERNEL is not set (the llm kernel stack, e.g. ~/llm_kernel)`。eca kernel 身上通常沒有這個變數，只想看有哪些腦包也得先自己找路徑。
- 建議：沒設時到 `$AOS_DAEMON` 的 procs 裡找 llm kernel 並列出；或加 `--kernel NAME`。
- 痛的程度：小不便
- 提出者與日期：ok-pilot 2026-11-14
- 出處：wf/temp/ok-pilot/aos-advice/小坑三則.md 第 1 則；wf/temp/ok-pilot/notes.md 第一輪「摩擦」第 4 點
- 狀態：未處理
- 相關：[fsm 範本「漏設 AOS_LLM_KERNEL」](fsm範本.md)，同樣是「找不到 kernel 要自己帶路徑」。

## before_verdict hook 拒信只能回 HookRejected，做不了「額度用完、晚點再試」

- 主題：kernel 與額度
- 哪裡：`lib/aos/kernel_llm` 的 `before_verdict` hook（README「hooks」表）；agent-fsm `wait.py` 只對 BudgetMissing 走冷卻。
- 現象：hook 退 10 一律回 `{"error": {"code": "HookRejected", ...}}`。agent-fsm 只對 `BudgetMissing` 走 AK17 冷卻重試，`HookRejected` 當一般 BrainFailed，agent 會停。所以想用 hook 外加額度規則（例 llmk2 的部門配額）時，只能直接殺掉那封請求，不能叫它晚點再來。
- 建議：讓 `before_verdict` 能在 stdout 回 `{"error": {"code": "BudgetMissing", "msg": "..."}}`，站照這個代號回信（代號白名單：BudgetMissing、HookRejected）。外加額度規則就不用改站本體。可和上一條的結構化欄位一起做。
- 痛的程度：小不便（規劃時發現，擋住「用 hook 做部門額度」這條路）
- 提出者與日期：ok-llmk2 2026-11-14
- 出處：wf/temp/ok-llmk2/aos-advice/kernel-llm-hook-reject-code.md；proto8/thinking/2026-11/14/llmk2-1114/03-計劃.md §2.3
- 狀態：已解（ok-kmsg，d6a564191）。改在共用的 `lib/aos/kernel/hooks.py`：`before_verdict`／`after_verdict` 的 hook 退 10 且 stdout 印 `{"error":{"code":"BudgetMissing","msg":"…","resets_at":"…"}}` 就回 BudgetMissing，回信帶 `resets_at`、`scope: "hook"`、`hook: <名>`，agent-fsm 照 313ce20ec 的冷卻等到 `resets_at`；不給 `resets_at` 照 30 秒起加倍的間隔重試。hook 給的 `window` 等其他鍵不帶（要對方停下照舊印純文字＝HookRejected）；其他 stdout 行為不變。等換樹才在活樹生效。設計與 Argon 採納表：proto8/thinking/2026-11/14/ok-kmsg-1114.md。

## llm kernel 沒開時，外人只看到 listen 逾時、沒有提示

- 主題：kernel 與額度
- 哪裡：`proto8/templates/daemon-root/README.md`（「它沒開時 agent 只是一直等、不會壞」那句）；`aos-agent … listen`；`aos-daemon-ctl ls` 的 REASON 欄。
- 現象：範本 README 有寫 llms 要放在專案旁邊（`.env` 預設 `AOS_LLM_KERNEL=${AOS_WS}/../llms/stacks/llm`）。但照文件打字的外人如果漏起了 llms、或擺的位置不同，agent 會一直等；他看到的只是 `timeout 60 … listen` 時間到、什麼都沒印，不知道是腦沒開。投稿隊是照 README 推的，**沒實測這個情況**。
- 建議：
  1. `listen` 等不到時，如果發現 agent 正在等腦，印一行「agent 在等 llm kernel（找的是 <路徑>）；沒開就照範本 README 起一個，或設 AOS_LLM_KERNEL」。
  2. 或讓 `aos-daemon-ctl ls` 的 REASON 欄標出「等腦」。
- 痛的程度：投稿沒寫；整理者看是拖慢（對照文件第一次用的外人來說可能擋路）。
- 提出者與日期：ok-release 2026-11-14
- 出處：wf/temp/ok-release/aos-advice/腦沒開時listen只會逾時.md；templates/daemon-root/README.md；草稿「開始用」第 3 步與疑難排解「agent 不回」一節（proto8/thinking/2026-11/14/release-1114/06-草稿/v1/_src/docs/zh/）
- 狀態：已解（ok-kmsg，d6a564191；採建議 1）。agent-fsm 的 wait 寄出請求後記 `think/brain_wait.json`（信名、kernel stack）；`aos-agent listen`／`say`／`ask`（含 `subagent` 工具的 ask／listen）發現 agent 在等腦而 kernel 的 `state.json` 不在、phase 不是 running／waiting／stopping 或 pid 不在時，stderr 印一行 `NAME is waiting for its brain, but the llm kernel at <路徑> is not running (…)`，逾時的 AnswerMissing 行尾也帶同一句；kernel 資料夾不在時印 `NAME cannot reach its brain: …`。`cmd/aos-agent` 那半已生效，`wait.py` 等換樹；建議 2（`ctl ls` 的 REASON 標等腦）沒做。10 分鐘的 stderr 警告照舊。
- 相關：[fsm 範本「漏設 AOS_LLM_KERNEL 時 agent-fsm 靜靜卡住」](fsm範本.md)（已解，只管變數沒設；有設但 kernel 沒開這條沒管）。

## eca 當 gate 時，下屬的唯讀查詢也被 hold，連讀信都 KernelFailed

- 主題：kernel 與額度（kernel_gate）
- 哪裡：`proto8/lib/agent/kernel_gate/hold`、`triage`；下屬帶 `AOS_KERNEL` 時 aos 工具經 gate 查自己的 stack 路徑（body 帶 `procs_state_path`）。
- 現象：skyrim 那邊的 eca（skyrim-agent-agentctl）掛在開了 gate 的 eca 底下，帶 `AOS_KERNEL` 的 aos 工具呼叫都經 gate；連讀信這種只查路徑的請求也被 hold，gate 忙時 3 秒逾時回 `KernelFailed`，要等一下重試。11-14 下午它自己累計 9 次（開場、寄 DONE、讀信都有），工人另回報 2 次。
- 建議：投稿沒寫；整理者看：只查路徑、不起東西的請求不該被 hold。
- 痛的程度：拖慢（每次都要重試）
- 提出者與日期：skyrim-agent-agentctl 2026-11-14（skyrim-agent 轉來，頂層 14:27 回過信）
- 出處：`~/repo/moddings/skyrim/agentctl/tmp/aos/skyrim-agent-agentctl/notes.md`「踩到的」第 1 條、「14:2x 追加」「14:3x 狀態」的逾時累計；底座部 ok-kf 查證
- 狀態：已解（c3c1877ea，ok-kf 11-14）：kernel_gate 的 hold、triage 看到 body 的 procs_* 只有 `procs_state_path: true` 就直接放行（不留，triage 記一行 pass），跟其他鍵並寫才照其他鍵判；測試 test_query_daemon（真 daemon，3 秒內回到原寄件人）。活樹待換樹（活樹的 lib 是另一份，11-14 晚換樹才生效）。
- 相關：本檔「gate 站掛在主人的 on_clock，主人長回合時下屬逾時」（同一個 KernelFailed 的另一半成因，還沒解）。

## gate 站掛在主人的 on_clock，主人長回合時下屬逾時

- 主題：kernel 與額度（kernel_gate）
- 哪裡：kernel_gate 的框架站靠開 gate 那隻 agent（主人）的 on_clock hook 推進。
- 現象：主人正在跑一個長回合時，站不跑，下屬經 gate 的請求等不到，3 秒逾時回 `KernelFailed`。上一條修好之後，唯讀查詢不再被 hold，但要經站處理的請求遇到主人長回合仍會逾時（頂層 14:27 給 skyrim 那邊的信也這樣說）。
- 建議：投稿沒寫。這是目前的設計使然（站跟著主人的鐘走），怎麼改由 ok-kf 出設計。
- 痛的程度：拖慢
- 提出者與日期：skyrim-agent-agentctl 2026-11-14（skyrim-agent 轉來）
- 出處：同上一條；頂層 11-14 14:27 給 skyrim-agent-agentctl 的信（筆記「14:3x 狀態」有記）；底座部 ok-kf 查證
- 狀態：已排入（ok-kf，11-15 出設計）。

## subagent add 之後馬上 ask，回 SubagentMissing，工人被從名冊刪掉

- 主題：kernel 與額度（只設 AOS_KERNEL 時的 subagent）
- 哪裡：`proto8/lib/agent/subagent/_entry`（名冊 subagents.json、對帳）。
- 現象：skyrim 那邊的 eca 帶 `AOS_KERNEL`、經 gate 掛工人：`subagent add` 後馬上 `ask`，回 `SubagentMissing`，工人被從名冊刪掉，但工人其實活著（`aos-daemon-ctl -d $AOS_DAEMON ls` 查得到）。名字也不能再用，下一隻只好換名。繞法：改用 `mailbox_send` 派工，叫工人做完自己 `self_ctl rm`。
- 建議：投稿沒寫。
- 痛的程度：拖慢（要換名、改走寄信派工）
- 提出者與日期：skyrim-agent-agentctl 2026-11-14（skyrim-agent 轉來）
- 出處：`~/repo/moddings/skyrim/agentctl/tmp/aos/skyrim-agent-agentctl/notes.md`「踩到的」第 2 條；底座部 ok-kf 查證
- 狀態：已解（c3c1877ea，ok-kf 11-14）：活樹的 lib 是舊的才會這樣。新版 subagent、fork 以 `ctl who` 回的自己那列 stack（絕對路徑）為基準，叫 aos-agent 不帶 `--daemon`、照 kernel 路由，subagents.json 存絕對路徑；只設 AOS_KERNEL、沒有 AOS_DAEMON 也能掛子、對帳、收子（新測試 kernel_fixture）。活樹待換樹（11-14 晚換樹才生效，換樹前照舊用 mailbox_send 派工）。
