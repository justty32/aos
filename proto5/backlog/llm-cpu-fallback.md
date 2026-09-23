# 問模型的 endpoint 換手

> 等 agent 規範重寫後再判。

**重架構後**：llm cpu 不再是一種 cpu，只是環境裡有 `llm-http` 的普通 exec cpu（[cpu §4.1](../spec/cpu.md)）；換手變成「問模型的那支程式」（`llm-http`／之後的 `aos-llm-call`，[kernel §8](../spec/kernel.md)）的事，`models` 表放哪要看 agent 重寫。

**問題**：agent 只寫模型代號，由 `models` 表對到 endpoint。某個 endpoint 壞掉（連不上、限流）時，現在只會回 `ok:false`。

**使用者期望（2026-09-22）**：這種事由問模型那一層處理（當時說的是 llm cpu），例如同一代號列多個 url、壞了換下一個。

**為什麼現在不做**：第一版一個代號一個 endpoint；重試與換手的規則要另定（幾次算壞、換完要不要換回）。

**以後從哪下手**：`models` 表（舊 `spec/llm-cpu.md` 那張，新位置待定），一個代號改成一串。
