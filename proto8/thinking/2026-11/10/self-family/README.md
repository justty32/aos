# self-family（11-10 晚）：給腦改自己的一家子——self_history 與 `aos-agent history`

← [11-10](../README.md)

self_tools、self_llm 在 [self-tools](../self-tools/README.md)；這夾記 self_history 這條線（人用的 `aos-agent history`、包它的 `self_history`、eca 縮水版）。self_hook 還在談、不做。

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
