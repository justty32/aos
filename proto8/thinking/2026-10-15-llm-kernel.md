# 2026-10-15 LLM kernel：請求自己填優先級

← [討論紀錄](README.md)｜前情：[kernel 截流](2026-10-15-kernel-intercept.md)（閘門／信箱草案、六題照建議預設定案）｜規範：[N-42](../NORMS/09-kernel.md)、[N-16 信箱](../NORMS/05-基礎設施-窗.md)｜概念：[C-47、C-11、C-13](../CONCEPTS/04-kernel.md)｜[`_metainfo`](2026-10-13-json-path/02-metainfo.md)

## 原文（10-15，照記）

「管LLM那塊，這塊很多時候都是確定性的，比如根據誰先來，誰就先上，或是根據token消耗量是否見底來看看說要不要擋，這個沒啥可說的，但我這邊想要提個：在"請求.json"的格式這塊，可以由發送者自己填寫一個優先級key，比如發送者覺得自己不急，那就填低一點，如果很急，那就填一個obj，裡面包括分級、分類、時限等。」

「隨意。我們可以先只處理priority和deadline兩個就好。json就是這點好，因為可以隨意擴充key，反正我們只要處理我們認得的。有需要再用json schema去限制。」（答六題未決）

## 決定（使用者 10-15 定）

- **LLM kernel 的基本規則是確定性的**：誰先來誰先上；token 額度見底就擋。不用腦判斷。
- **請求.json 有一個發送者自己填的優先級 key**：不急就填低一點（簡單值）；很急就填一個物件，裡面有分級、分類、時限等。

## 結論（AI 整理，待使用者確認）

- **key 的形狀**：`priority`，三種寫法都收——簡單值 `"low"`／`"high"`／數字 `3`；物件 `{"level": "high", "class": "chat", "deadline": "2026-10-15T18:00:00+08:00"}`，欄位都選填。kernel 先正規化：簡單值＝`{"level": 那個值}`；沒寫＝`{"level": "normal"}`，照先來先上排；不認得的欄位照帶、不報錯。
- **跟 `_metainfo` 的分工**：`_metainfo`＝被叫 inst 作者自報（靜態、跟著定義）；`priority`＝呼叫者這一次多急（動態、跟著請求）。排序先看 `level`，同級再看 `_metainfo`（樹淺的先、便宜的先），都一樣就先來先上；`_metainfo` 從不蓋過 `level`。
- **誰填**：不由腦或 agent 填（C-20），由**閘門**抄進信裡（閘門設定的 `priority`；10-15 深夜 KISS 1.9 拿掉 `AOS_PRIORITY` 後備，只認 gate.json）。子 agent 想更急得自己在它的閘門設定寫。
- **token 額度**：放 kernel 自己的 state 窗（例 `{"budget": {"used", "limit", "since"}}`），每封回信的 usage 加上去；閘門、agent 都不知道額度存在。見底＝不排隊、直接回 N-29 的錯 `BudgetExhausted`，閘門照吐，agent 走 `BrainFailed`。快見底時可留一段只給 `high` 過（保底）。
- **第一版只處理 `priority`（level）與 `deadline` 兩個**；其他 key（`class` 等）照樣帶著、kernel 不認就不管；需要時再用 JSON schema 限制。`class` 出本版範圍。
- 其餘六題使用者「隨意」＝照建議預設定案（10-15 使用者『隨意』，照建議）：
  - `level` 名字 `low`／`normal`／`high`，數字也收（`<0`／`0`／`>0`）。
  - `deadline` 兩者：越近越前排；到達時已過期不跑、回 `DeadlineMissed`。
  - 濫用：先信任，之後再加每發送者配額。
  - aging：每等 10 拍升一級。
  - token 額度：全局、usage total tokens、一天一期歸零。

## 未決

無（`class` 排序、每發送者配額留待之後）。

## 動工自定點

10-15 做了基礎實作（lib kernel.md（已刪，見 git 歷史 aa2fec1f）），自己定的、等使用者看：

- 名字：閘門 `aos_gate.py`、身體 `aos_gate_kernel.py`；信箱 `tmp/ new/ cur/ reply/`。
- `deadline`：ISO 字串或 epoch 秒；剩不到 `near_ms`（30 秒）插隊，同級也是近的先。
- `_metainfo` 的「便宜」看 `cost`（數字，沒寫＝0）。
- aging 不封頂：等久了 low 可以超過 high。
- 一拍＝跑一次身體（閒的拍也算）；`slots`>1＝同一拍幾封一起跑，等最慢的。
- target 在 kernel 的環境跑，不帶呼叫者的環境變數。

（原有的 `wait_ms` 一條被 KISS 1.8 刪；「自己的錯退 125」被 10-15 晚「自己的錯全改退 1」取代，見 [原則 § 決定](2026-10-15-principles.md#決定)。）

## 實跑：LM Studio 真腦包閘門（10-15）

使用者 10-15「把 LM Studio 的真腦包上閘門實跑一次」。kernel 在 aos-daemon 底下（`slots` 1），報時員巢狀：boss（閘門 `normal`）→ clerk（閘門 `high`）→ clock；**兩個同時問「現在幾點？」**（A、B），腦＝Qwen3-1.7B（`-c 4096`），逾時拉大（腦 180 秒、tool 900 秒、`wait_ms` 600 秒）。共 7 次 chat 請求，約 34 秒；收尾無殘留。

- **端到端通了**：A 的 clerk 叫了 clock，回「現在是12:52:15。」（真時間）；B 的 clerk 沒叫 clock、編了 `08:35:12`，boss 照轉（同 [clerk-live](2026-10-15-clerk-live.md)）。
- **服務順序**（tick 1→7）：A-boss、B-boss（normal，先來後到）→ clerk 的 high 三封 → A、B 的 boss 收尾。每封 3.8～5.4 秒；排隊等：B-boss 3.8 秒、第一封 clerk 約 4.2 秒（**不搶佔跑到一半的**）。巢狀是串的，沒出現 high 插 normal 的隊（插隊由單元測試、假腦 demo 證）。
- **`waited` 恆為 0**：`slots` 1 時 tick 只在服務時才走（7 拍 7 封），aging 以拍計，慢腦＋一格下幾乎不觸發；看排隊要看 `sent` 與回信時間。
- **token 額度沒計到**（`budget.used` 0）：`aos_brain_openai.py` 丟了 `usage`。使用者「都隨意」→ 已補：兩顆腦在 assistant 訊息頂層帶 `usage`（stdout 仍一份＝N-12 最後一份），think 接進 history 前拿掉；kernel 不用改。
- **相對路徑**：閘門 `target` 從**呼叫者的 cwd** 算（不是從 gate.json），所以寫成 `../lm.json`；寫成 `lm.json` 得 `ReadFailed`。

## 順手修：測試漏行程（10-15）

- 早上起累積約 75 支孤兒 `aos_loop.py -`：test_daemon 收尾對 daemon 送 SIGKILL，子 loop 自成 session、不跟著死（設計如此，`load` 接回靠它）。
- 修：收尾改 SIGTERM（等不到才 SIGKILL）；`helpers.Tmp` 刪暫存資料夾前查 cwd 在裡面的 aos_loop／aos_daemon，還活著＝砍掉並算失敗。daemon 行為不改。
