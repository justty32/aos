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
- 狀態：未處理。2368ee3af（AK17）只解了「被拒就停下」：現在會冷卻重試並 brain_notify 通知 mom。這條要的結構化欄位還沒有，llm_rules.py 的拒絕仍只回 (code, msg) 文字。

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
