# self-family（11-10 晚）：給腦改自己的一家子——self_history 與 `aos-agent history`

← [11-10](../README.md)

self_tools、self_llm 在 [self-tools](../self-tools/README.md)；這夾記 self_history 這條線（人用的 `aos-agent history`、包它的 `self_history`、eca 縮水版）。self_hook 這條線在 [hook](hook/README.md)。

## 使用者原話（逐字）

- self_tools（原則出處）：「我原本想說，這支工具就是aos-agent tools的包裝，只是目標改自己」；路徑限制「A，拿掉限制」。
- 「好。對了，你覺得self_brain這個工具有需要嗎？以及self_history？」
- 「還有self_hook，用於在有東西進到queue，或是一些事件發生，比如呼叫了某特定工具，比如brain呼叫失敗，或是新增了某些特定工具之類時，執行指定aos函數。self_brain來做吧，但改名self_llm。self_history要來寥寥。等這些都好了，就回來看agents」
- 頂層就 self_history 問五題：1 給哪些動作（看／刪一段／把一段換成摘要／任一行隨便改）；2 正在進行的這一步（腦叫 self_history 的那則 assistant 訊息與其工具結果）動不了、只能改它之前的；3 改掉的原文留不留底；4 eca 的對話在 claude／codex 那邊、aos 改不到，接受只有 fsm 有，或 eca 給縮水版（例：開一段新對話、帶一段摘要過去）；5 照包裝原則人用的指令也要有 `aos-agent history`、self_history 再包它（順便解 10-30「停著時改 history 再繼續」）。使用者答：「1.全給，風險自己擔。2.可以。3.可選，默認搬到旁邊(可以選要搬到哪) 4.接受縮水版。5.對」

## 決定

- 四級動作全給（看、刪一段、一段換成摘要、任一行隨便改），風險使用者自擔。
- 正在進行的這一步動不了，它之前的隨便改。
- 改掉的原文：預設搬到旁邊一個檔、可選搬到哪、也可選不留。
- eca 給縮水版。
- 人用的 `aos-agent history` 先有，`self_history` 是它的純包裝（目標＝自己）；10-30 [「停著時改 history 再繼續」](../../../2026-10/30/eca/09-方向題.md#之後再改停著時改-history-再繼續10-30使用者先記下)由它解。

## 檔案

| 檔 | 是什麼 |
|---|---|
| [01-施工結果](01-施工結果.md) | 每個 commit 做了什麼、驗收、代定清單、eca 真對話驗收（haiku）、給知識庫的節點內容 |
| [02-self_state與self_ctl](02-self_state與self_ctl.md) | 使用者 self_peek 五題、self_ctl 三題原話與決定 |
| [03-self_state與self_ctl施工結果](03-self_state與self_ctl施工結果.md) | 動作與例子、commit、驗收（假腦、gemma、eca haiku）、代定 8 條、知識節點內容 |
| [hook/](hook/README.md) | self_hook 那條線（另一隊） |

## 做了（11-10 晚）

`aos-agent history`（ls／rm／summarize／set，原文搬到 `history_removed.jsonl`）→ `self_history` 包裝（這一步鎖著）→ eca 縮水版（history 被改過＝下一輪開新對話）→ 文件。假腦、gemma 真腦、eca haiku 真對話都驗過。細節見 [01](01-施工結果.md)。

**11-10 深夜改**：`summarize` 寫進去的那則內容固定成 `aos: summary (lines A-B, N messages): 摘要`（角色照舊預設 user；`set` 不套）。使用者「self_history的摘要這塊，身份可以是user，只是內容這塊希望能符合特定格式，比如我們現有的error那樣，就aos:...。」見 [tonight-rulings](../tonight-rulings/README.md) 題 8。
