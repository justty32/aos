# 2026-10-15 agent 判官實跑（LM Studio Qwen3-1.7B）

← [討論紀錄](README.md)｜前情：[通用 kernel](2026-10-15-general-kernel.md)

## 原文（10-15）

使用者要求：用 LM Studio 實跑一次 agent 判官（kernel 的 `judge` 換成 `judge-agent.json`，判官的腦直連 `qwen/qwen3-1.7b`、不走本 kernel），跑 demo 情境（llm／cpu／human 搶）。

## 結論（AI 整理）

- 判官單獨問一次可用（回的形狀合法、high 先），但在 kernel 底下太慢（一次 1～2 分鐘）、常回空字串退回規則，demo 的等待上限擋不住；agent 判官沒能改變服務順序（＝規則判官的順序）。
- 慢與空回覆的原因：state 窗整份輸入大，加上 Qwen3 先想、把輸出長度耗光（→ 下面兩項決定）。

## 未決的回答（10-15 使用者）

「我覺得不用想...因為以後實際去使用那些厲害模型的 endpoint 如 claude/gpt，會發現他們都會把思考過程加密，或是乾脆不給，聲稱是為了防蒸餾。剩下都隨意」

1. **不靠模型思考**：判官 `judge/system.md` 開頭 `/no_think`；aos 從不依賴思考內容，只算最後的答案。
2. **判官輸入瘦身**（隨意，照建議）：stdin＝state 窗只留 `queue`／`running`／`slots`／`budget`（同一份物件的子集，C-48 不新增格式），兩種判官都這樣。

## 重跑（10-15，`/no_think`＋瘦身後）

**結論（AI 整理）：快了（每次幾秒）、每次都合法，但 1.7B 判官每次都「全部 defer」，kernel 因此卡住。**

- **判官全 defer＋格全空＋沒有新信＝永遠卡住**（規則判官不會，agent 判官會）：局面不再變，照「局面沒變不問」不再問，閘門一直等。使用者選了下面的補位。
- demo 被中斷時不收自己丟出的閘門（閘門沒寫 `wait_ms`＝不限），要手動收。

未決：無（「換大一點的模型再試」10-21 使用者裁定結案）。

## 決定：補位（使用者 10-15「照建議做補位」）

套完判官的決定後還有空格，就用確定規則從沒被 reject 的剩下的信補滿；判官的 `defer`＝「不是我挑的」。log 的 `decide.backfill`、`start.reason`＝`backfill`。全 defer 不再卡住。

補位之後的實跑見 [judge-live2](2026-10-15-judge-live2.md)。
