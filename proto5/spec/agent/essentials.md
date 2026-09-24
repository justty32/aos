← [agent](README.md)｜[spec 總導航](../README.md)

# 使用者只需要懂的（09-24 試玩 r2 補）

`aos-agent init` 生的家（[aos-agent.md §1.1](../aos-agent/cli.md)）長這樣，人會碰的只有前四樣：

| 東西 | 是什麼 | 常改的 |
|---|---|---|
| `info.json` | 設定（§3） | `llm.model`＝模型**代號**（真名、endpoint 在 llm cpu 那邊的 llm.json）；`llm.timeout_ms`＝一次問模型最多跑多久（外圈，要比 llm.json 的 HTTP 逾時大）；`tools`＝工具檔或資料夾；`tick.interval_ms`＝多久走一格 |
| `prompts/system.json` | 人格：`{"content": "…"}` | 內容 |
| `tools/*.json` | 工具（§3.3）：OpenAI `tools` 陣列，每個元素多一格 `_meta`（跑什麼） | 見下 |
| `input/`（或 `input.json`） | 輸入：放一個檔＝一則話；用 `aos-agent say` 投就不用管格式 | — |
| `prompts/history.json` | 記憶，程式寫 | 別在它跑的時候改 |
| `state.json`、`work/`、`done/`、`log/` | 程式的進度、工作區、收過的輸入、錯誤紀錄 | 出事看 `log/agent.err`、`log/llm.err` |

**工具**：一支程式，**stdin 收模型給的 arguments（JSON 字串原樣）、stdout 印的東西原樣給模型看**。`_meta.argv[0]` 含 `/` 就是相對 agent 家的路徑（要有執行位），
不含 `/` 就照 cpu 的 PATH 找；cwd 預設是 agent 家；`_timeout_ms` 預設 60000。改完工具檔下一格就生效，壞了 `log/agent.err` 會指出哪個檔第幾個元素。

卡住、壞掉、怎麼恢復，看 [aos-agent.md 的「使用者只需要懂的」](../aos-agent/README.md)。
下面 §2 以後的指示詞規則、§4.3 `batch`、§4.4 恢復紀錄是程式自己用的，日常不用讀。
