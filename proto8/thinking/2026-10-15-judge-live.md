# 2026-10-15 agent 判官實跑（LM Studio Qwen3-1.7B）

← [討論紀錄](README.md)｜前情：[通用 kernel](2026-10-15-general-kernel.md)｜程式：lib kernel.md（已刪，見 git 歷史 aa2fec1f）、demo `proto8/demo/kernel2/`

## 原文（10-15）

使用者要求：用 LM Studio 實跑一次 agent 判官（kernel 的 `judge` 換成 `judge-agent.json`，判官的腦直連 `qwen/qwen3-1.7b`、不走本 kernel），跑 demo 情境（llm／cpu／human 搶）。

## 條件

- 程式：commit `2abedf16`（`git archive` 抽到暫存夾跑，沒動 repo）。LM Studio `qwen/qwen3-1.7b -c 4096 --ttl 600`；收工 `unload --all`、`server stop`，沒留行程。
- 情境同 `run.py`：8 封（L-low、C1、H1、L-normal、C2、L-high、H2、C3），格數 llm 1、cpu 2、human 1。

## 結論（AI 整理）

**這次沒跑成一個完整的、判官全程接上的情境；判官單獨可用，但在 kernel 底下太慢，被 demo 的等待上限與連錯額度吃掉。**

1. **單獨問一次（3 封 llm／llm／human）**：回 `{"run":["b"],"defer":["a","h"],"reject":[]}`，合法、high 先（但 human 有空格卻被 defer，沒照「human 先」）；**14.6 秒**。
2. **進 kernel 跑完整情境**：兩輪都被 demo 的 `p.wait` 擋住（60 秒、400 秒）拋 `TimeoutExpired`，手動收掉；daemon 正常收工、沒漏行程。demo 的 `p.wait(60)` 跟 agent 判官不相容（每拍動輒 > 60 秒）。
3. 第二輪 kernel 問判官 4 次：**106.8 秒**空字串（`JudgeReplyBad`，退回規則）；**102.0 秒**空字串（退回規則）；**67.1 秒**合法 `run 2、defer 1`（high 先、low 再等）；**112.6 秒** `BrainFailed`。
4. 數字總結：解析成功 2／6 次；退回規則至少連續 2 次；延遲 15 秒（單獨）～67–113 秒（kernel 內），遠長於 demo 的 0.6–1.5 秒活；服務順序＝規則判官的順序（low 先到先跑），agent 判官沒能改變它；最終順序未完整驗證。約 10～12 次 chat 請求。
5. kernel 內慢、空回覆的推測：state 窗整份輸入大＋Qwen3 先想把輸出長度耗光（→ 下面兩項決定）。

## 未決的回答（10-15 使用者）

「我覺得不用想...因為以後實際去使用那些厲害模型的 endpoint 如 claude/gpt，會發現他們都會把思考過程加密，或是乾脆不給，聲稱是為了防蒸餾。剩下都隨意」

1. **不靠模型思考**：判官 `judge/system.md` 開頭 `/no_think`；原則寫進 lib agent.md（已刪，見 git 歷史 aa2fec1f）——aos 從不依賴思考內容，只算最後的答案。
2. **判官輸入瘦身**（隨意，照建議）：stdin＝state 窗只留 `queue`／`running`／`slots`／`budget`（同一份物件的子集，C-48 不新增格式），兩種判官都這樣（kernel2.md（已刪，見 git 歷史 aa2fec1f））。
3. **重跑**：見下節。

## 重跑（10-15，`/no_think`＋瘦身後）

條件：工作樹（含上兩項）複製到暫存夾跑；demo 等待上限拉到 600 秒、只跑第 1 段；`ask_judge.py` 副本記每次輸入／原始回覆／耗時，並設 13 次上限。LM Studio 同上（`qwen/qwen3-1.7b`，`-c 4096`），判官直連、不走本 kernel。收工 `unload --all`、`server stop`，server 確認關、沒留 daemon／loop／閘門行程。

**結論（AI 整理）：快了、每次都合法，但 1.7B 判官每次都「全部 defer」，kernel 因此卡住，情境沒跑完。**

1. **判官呼叫 5 次**（kernel 內 2 次＋同一份輸入再問 3 次），chat 請求 5 次。
2. **延遲 4.9～7.4 秒**（輸入 868／1307 bytes），比上輪 67～113 秒**快約 15 倍**。
3. **解析 5／5 成功、空回覆 0、退回規則 0**。
4. **決定不合理**：5 次都是 `run: []`、所有 id 進 `defer`——格全空，human 沒先、high 沒先；同一份輸入連問 3 次一模一樣。
5. **最終服務順序：無**（0 封被服務）。局面不再變＝照「局面沒變不問」不再問，8 個閘門一直等；約 30 秒手動中斷，daemon 正常收工，閘門用 SIGTERM 撤信。

挖到的：**判官全 defer＋格全空＋沒有新信＝永遠卡住**（規則判官不會，agent 判官會）。當時攤的三條路：全 defer 又有空格時當判官錯、隔一段時間再問、system.md 加一句「有空格就要 run」；使用者選了下面的補位。另：demo 被中斷時不收自己丟出的閘門（閘門沒寫 `wait_ms`＝不限），要手動收；`/tmp` 下有不少 `aos-fsm-*`（`aos_methods.py` 的 mkdtemp）殘留夾，來源不明，沒刪。

## 未決（待使用者）

1. 判官要不要換大一點的模型再試（例 qwen3 4B／8B），或先改 system.md 再試 1.7B？（原第 1 題「全 defer 卡住要不要防」已由下節補位解。）**（10-21 使用者裁定：結案。）**

## 決定：補位（使用者 10-15「照建議做補位」）

套完判官的決定後還有空格，就用確定規則從沒被 reject 的剩下的信補滿；判官的 `defer`＝「不是我挑的」。log 的 `decide.backfill`、`start.reason`＝`backfill`。細節見 kernel2.md（已刪，見 git 歷史 aa2fec1f）。上節「未決 1」就此解（全 defer 不再卡住）。

後續：補位之後的實跑見 [judge-live2](2026-10-15-judge-live2.md)。
