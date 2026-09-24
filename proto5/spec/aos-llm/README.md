← [spec 總導航](../README.md)

# aos-llm：問模型（程式規範）

← [proto5 README](../../README.md)｜資料夾：[agent.md](../agent/README.md)｜誰叫它：[aos-agent.md](../aos-agent/README.md)｜它跑在哪：[cpu.md §4.1](../cpu/methods.md)、[kernel.md §1.1](../kernel/home.md)

> 第 2 版，2026-09-24 定稿，2026-09-24 fix-r4 改命令列（`aos-llm-call` 改成 `aos-llm call`）；已實作（`lib/aos_llm_call.py`＋`cli/aos-llm`）。輪次、審查與實作沿革在檔尾〈沿革〉（09-24 試玩 r3 搬）。

一句話：**`aos-llm call AGENT_DIR` 讀 agent 的模型輸入與這顆 cpu 的模型表，呼叫一次模型，把一則 assistant message 印成一行 JSON。**
它不寫記憶、不碰 `state.json`、不跑工具，跑完就走。它是 kernel 排給 llm 池某顆 cpu 的一份普通工作；
模型表、金鑰、`aos-llm call` 自己在哪，全是那顆 cpu 的環境給的（「cpu 的環境＝工作的環境」）。

## 9. 已拍板的前提（使用者定的，不重問）

1. **沒有同步工具**：問模型是往 kernel `add --once` 的普通工作，這支程式就是那件工作的 `argv[0]`。取捨：最快也要等一格 tick。
2. **agent 先進現有的池**：問模型派往 `info.llm.pool` 那個現有的池，不給 agent 開專屬 cpu。
3. **llm.json 放 llm cpu 那邊**（cpu 的環境＝工作的環境）：模型表（endpoint／真名／api_key／timeout_ms）跟 aos-llm call 同住，
   靠那顆 cpu 的 `envs` 設 `AOS_LLM_CONFIG=/abs/llm.json` 找到；agent 的 `info.llm` 只剩 `model`、`params`、`pool`、`timeout_ms`。

## 8. 這份沒管的

串流、重試、多個 choices、token 計數；記憶太長；llm.json 的管理介面（使用者構想的 `aos-agent llms`，[thinking/aos-agent.md](../../../thinking/aos-agent.md)）；
同一顆 cpu 服務多份不同的 llm.json（要不同表就開不同池的 cpu）。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔（`history.md`、`impl-notes.md`、`rulings.md` 等）。

| 檔 | 內容 |
|---|---|
| [usage.md](usage.md) | §0 名詞；§1 用法與環境；§7 給程式用 |
| [config.md](config.md) | §2 `llm.json`（模型表） |
| [request.md](request.md) | §3 讀 agent 家；§4 組 body；§5 HTTP、驗、輸出 |
| [timeouts.md](timeouts.md) | §6 兩個逾時各管什麼 |
| [rulings.md](rulings.md) | 調度者裁決（第 2～3 輪，實作層級） |
| [history.md](history.md) | 沿革 |
