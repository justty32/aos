# llm cpu 的 endpoint 換手

**問題**：agent 只寫模型代號，llm cpu 家的 `models` 表對到 endpoint。某個 endpoint 壞掉（連不上、限流）時，現在只會回 `ok:false`。

**使用者期望（2026-09-22）**：這種事由 llm cpu 處理，例如同一代號列多個 url、壞了換下一個。

**為什麼現在不做**：第一版一個代號一個 endpoint；重試與換手的規則要另定（幾次算壞、換完要不要換回）。

**以後從哪下手**：`spec/llm-cpu.md` 的 `models` 表，一個代號改成一串。
