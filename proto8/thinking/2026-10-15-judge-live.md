# 2026-10-15 agent 判官實跑（LM Studio Qwen3-1.7B）

← [討論紀錄](README.md)｜前情：[通用 kernel](2026-10-15-general-kernel.md)｜程式：[lib kernel.md](../lib/kernel.md)、demo `proto8/demo/kernel2/`

## 原文（10-15）

使用者要求：用 LM Studio 實跑一次 agent 判官（kernel 的 `judge` 換成 `judge-agent.json`，判官的腦直連 `qwen/qwen3-1.7b`、不走本 kernel），跑 demo 情境（llm／cpu／human 搶）。

## 條件

- 程式：commit `2abedf16`（`git archive` 抽到暫存夾跑，沒動 repo 的 lib／demo）。
- LM Studio：`server start -p 1234`、`load qwen/qwen3-1.7b -c 4096 --ttl 600 -y`；收工 `unload --all`、`server stop`，`lms ps` 空、server 關、沒留下我起的 daemon／loop。
- 為了記時間，暫存夾的 `ask_judge.py` 多寫了每次的輸入／原始回覆／耗時（只在副本）。情境同 `run.py`：8 封（L-low、C1、H1、L-normal、C2、L-high、H2、C3），格數 llm 1、cpu 2、human 1。

## 結論（AI 整理）

**這次沒跑成一個完整的、判官全程接上的情境；判官單獨可用，但在 kernel 底下太慢，被 demo 的等待上限與連錯額度吃掉。**

1. **單獨問一次（3 封 llm／llm／human 的小局面）**：回 `{"run":["b"],"defer":["a","h"],"reject":[]}`，合法、挑對了（high 先）；耗時 **14.6 秒**。（注意：human 那封被 defer；human 格有空，system.md 說 human 先，所以這次**沒照「human 先」**，只對了 priority。）
2. **進 kernel 跑完整情境**：兩輪，各被 demo 的 `p.wait` 擋住（第一輪 60 秒、第二輪我拉到 400 秒）而拋 `TimeoutExpired`，手動收掉；daemon 正常收工、沒漏行程。
3. 第二輪 kernel 實際問了判官 4 次（記下的）：
   - 第 1 次 **106.8 秒**，agent 回**空字串**→ 判官非 0 退出（`JudgeReplyBad`）→ judge_fails 1、這拍退回規則（一口氣認領 llm 1、cpu 2、human 1 四封）。
   - 第 2 次 **102.0 秒**，又是**空字串**→ judge_fails 2，退回規則。
   - 第 3 次 **67.1 秒**，回**合法** `run 2、defer 1`（run 的是 L-high 與一封 cpu，defer L-low），**判對了 priority**（high 先、low 再等）（judge_fails 因此歸零）。
   - 第 4 次 **112.6 秒**，腦呼叫失敗（`BrainFailed`）。
   - 第一輪另有 2～3 次呼叫沒機會記錄（被 60 秒擋住，未計）。
4. 數字總結：解析成功 2／6 次（單獨 1＋kernel 內 1；其餘 4 次空回覆或腦失敗＋未記錄的）；退回規則至少 2 次連續（judge_fails 到 2）；每次延遲 **15 秒（單獨）～67–113 秒（kernel 內）**，遠長於 demo 的 0.6–1.5 秒活；一輪下來規則退回後的服務順序＝規則判官的順序（low 的 llm 最先到就最先跑，因為 `L-low` 先丟、同資源先來後到），不是 human 或 high 優先，跟規則判官 demo 一致，agent 判官沒能改變它。最終順序未完整驗證（沒讓情境跑完）。
5. 請求量：約 10～12 次 chat 請求（含兩輪被殺的），不超過 15。

**奇怪處**：

- 單獨 14 秒、kernel 內 67–113 秒：state 窗整份（含 `running`、`seen`、`last_sig` 等）比我手寫的小局面大很多，加上 Qwen3 會先想，輸入大＋想得久；`--ttl`／parallel 4 也可能有排隊。
- 回空字串：疑似思考把輸出長度耗光（content 空）；`ask_judge.py` 取最後一句的 `{…}`，空就當 `JudgeReplyBad`。
- 第一輪被擋住時，LM Studio 端仍有判官請求在排，下一輪疊上去，可能讓第二輪更慢（污染）。
- demo 的 `p.wait(60)` 與 agent 判官不相容（判官每拍動輒 > 60 秒）。

## 未決（待使用者）

1. 判官用 Qwen3-1.7B 要不要壓住思考（`/no_think`、`max_tokens`、或換不想的模型）？現在慢又常空回。
2. 判官輸入要不要瘦身（只給 queue／running／slots，不給整份 state 窗）？
3. 要不要重跑（先解 1、2，demo 等待上限拉長，並先確認 LM Studio 沒殘留請求）？
