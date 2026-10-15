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

## 未決的回答（10-15 使用者）

「我覺得不用想...因為以後實際去使用那些厲害模型的 endpoint 如 claude/gpt，會發現他們都會把思考過程加密，或是乾脆不給，聲稱是為了防蒸餾。剩下都隨意」

1. **不靠模型思考**：判官 `judge/system.md` 開頭 `/no_think`；原則寫進 [lib agent.md](../lib/agent.md#思考介面腦)——aos 從不依賴思考內容，只算最後的答案。
2. **判官輸入瘦身**（隨意，照建議）：stdin＝state 窗只留 `queue`／`running`／`slots`／`budget`（同一份物件的子集，C-48 不新增格式），兩種判官都這樣（[kernel2.md](../lib/kernel2.md#state-窗判官的-stdin它的子集)）。
3. **重跑**：見下節。

## 重跑（10-15，`/no_think`＋瘦身後）

條件：工作樹（含上兩項）複製到暫存夾跑；demo 等待上限拉到 600 秒、只跑第 1 段；`ask_judge.py` 副本記每次輸入／原始回覆／耗時，並設 13 次上限。LM Studio 同上（`qwen/qwen3-1.7b`，`-c 4096`），判官直連、不走本 kernel。收工 `unload --all`、`server stop`，server 確認關、沒留 daemon／loop／閘門行程。

**結論（AI 整理）：快了、每次都合法，但 1.7B 判官每次都「全部 defer」，kernel 因此卡住，情境沒跑完。**

1. **判官呼叫 5 次**（kernel 內 2 次＋直接同一份輸入再問 3 次）；chat 請求共 5 次。
2. **延遲 4.9～7.4 秒**（輸入 868／1307 bytes）；上輪 67～113 秒，**快約 15 倍**。
3. **解析 5／5 成功、空回覆 0、退回規則 0**（`judge_fails` 一直 0）。
4. **決定不合理**：5 次都是 `run: []`、所有 id 進 `defer`——格全空（llm 1、cpu 2、human 1 都 0 用），human 沒先、high 沒先。同一份 8 封輸入連問 3 次一模一樣（穩定地錯）。
5. **最終服務順序：無**（0 封被服務）。kernel 第 1 拍問、全 defer；第 2 拍新信到再問、全 defer；之後局面（排隊名單、在跑名單、空格）不再變，照「局面沒變不問」就不再問，8 個閘門一直等。我在約 30 秒時手動中斷（不等 600 秒），daemon 正常收工，閘門用 SIGTERM 撤信。

**挖到的邊緣狀況（攤給使用者，不擅改）**：

- **判官全 defer＋格全空＋沒有新信＝永遠卡住**。規則判官不會這樣，agent 判官會。可能的方向（都是使用者的事）：全 defer 又有空格時當判官錯（退回規則、`judge_fails`＋1）；或隔一段時間就算局面沒變也再問；或 system.md 加一句「有空格就要 run」。
- demo 被中斷時不收自己丟出的閘門（閘門沒寫 `wait_ms`＝不限），要手動收。
- 小模型讀長 id（`0179…json`）可能吃力；判斷力不夠是模型的問題，跟速度問題分開看。
- 另見：`/tmp` 下有不少 `aos-fsm-*`（`aos_methods.py` 的 mkdtemp）殘留夾，來源不明（不是這次實跑留的），沒刪。

## 未決（待使用者）

1. 全 defer 卡住要不要防？防的話選哪種（見上）。
2. 判官要不要換大一點的模型再試（例 qwen3 4B／8B），或先改 system.md 再試 1.7B？

## 決定：補位（使用者 10-15「照建議做補位」）

套完判官的決定後還有空格，就用確定規則從沒被 reject 的剩下的信補滿；判官的 `defer`＝「不是我挑的」。log 的 `decide.backfill`、`start.reason`＝`backfill`。細節見 [kernel2.md](../lib/kernel2.md)。上節「未決 1」就此解（全 defer 不再卡住）。
