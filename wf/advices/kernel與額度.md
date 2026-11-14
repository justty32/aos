# kernel 與額度

← [README](README.md)

llm kernel（lib/aos/kernel_llm）、腦額度、找 kernel 的意見。

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
- 狀態：未處理（llm_rules.py 仍只認 HookRejected）

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
- 狀態：未處理。部分已有：agent-fsm 的 wait 現在等腦回信每滿 10 分鐘在 stack 的 stderr 印一行 `agent-fsm: warning: no reply from the brain for N minutes …; still waiting`（附信卡在 kernel 哪一格，見 templates/agent-fsm/README.md）；但這行只在 stderr.txt，`listen` 和 `ctl ls` 都看不到。
- 相關：[fsm 範本「漏設 AOS_LLM_KERNEL 時 agent-fsm 靜靜卡住」](fsm範本.md)（已解，只管變數沒設；有設但 kernel 沒開這條沒管）。
