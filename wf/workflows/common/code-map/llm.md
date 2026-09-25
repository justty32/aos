← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

## core/llm 與 core/agent

這兩個核心小專案合起來，讓 agent 活在 loop 推進的回合世界裡：`aos agent` 保存人格、對話、狀態與工具往返，loop 每回合從 `.aos/every/agent-<name>.json` 複製一條 `step`；`aos llm` 則是它直接連結的思考引擎，向 OpenAI 相容端點做一次非串流補全。工具的真登記表由 `core/tool` 放在世界層 `.aos/tools/<name>.json`；agent 層 `agents/<name>/tools.json` 若存在只是一張白名單，不存在就使用世界裡全部工具。工具往返的關鍵節奏是：**回合 N 投遞 → N+1 執行 → N+2 讀得到結果**。
agent 本身不 fork／exec 工具，只把 instruction 交給 world inbox；loop 負責匯聚、執行與落結果。
因此 agent 與 loop 透過公開 API 解析目前世界，再靠 `.aos/` 版面協作；思考、執行與結果回收各自落在不同回合。
送給模型的工具清單每項固定一行；模型呼叫的 `args` 必須符合登記的 `list`（字串陣列）／`string`（單一字串）／`none`（省略或空值）。工具執行結果與未知工具／args 形狀錯誤都以同一個 JSON envelope 當 `tool` message 回給模型：共同欄位是 `call_id`／`tool`／`args`／`ok`／`result`，失敗再加 `error.type`／`message`／`retryable`。
`aos agent` 不另開 `aos llm` 子行程，而是直接呼叫它的公開函式庫 API。

### `core/llm` 檔案表

| 檔案 | 負責什麼 |
|------|----------|
| `core/llm/include/aos/llm.hpp` | 公開 API：message／options／CLI options，以及環境設定、參數解析、request／response JSON、`parse_response_model()` 與帶可選 `served_model` 出參的 `complete()` 介面。 |
| `core/llm/include/aos/slot.hpp` | 公開槽 API：兩層 CPU 上限、取槽／自動放槽、`waiting-llm` 與槽狀態查詢。 |
| `core/llm/src/llm.cpp` | 函式庫實作：讀 `AOS_LLM_*`、組 OpenAI messages request、用 libcurl POST `<base>/chat/completions`，驗 HTTP 並抽出 `choices[0].message.content` 與實際 `model`。 |
| `core/llm/src/slot.cpp` | 使用者層與世界層上限合併，以 `flock` 槽與數字優先度等待票限制各 CPU 並行數，並統計佔用與等待。 |
| `core/llm/src/run.cpp` | `aos llm` CLI 層：完整 help、stdin prompt 或 `--messages` 檔案進站，處理 `--system`／endpoint／model／timeout／`--engine`／`--priority`，呼叫前取槽；`--slots` 顯示並行上限現況；端點實際模型不同時仍印回覆、另報兩個模型並回 1。 |
| `core/llm/tests/test_llm.cpp` | 離線驗環境／CLI 參數、messages 與 response JSON、實際模型抽取，以及 help 不連端點。 |
| `core/llm/tests/smoke_slots.sh` | 手動端到端 smoke：離線假端點驗槽串行、逾時退回、世界層限縮，以及 pi step 持有 provider 槽。 |
| `core/llm/README.md` | 使用入口、預設 LM Studio endpoint／model、`--engine`／`--priority`／`--slots`、兩層並行上限設定與錯誤語意。 |
