# aos-mcp

`aos-mcp` 讓 Claude 用工具操作 aos。

它走 stdio。每行是一個 JSON-RPC 2.0 訊息。
stdout 只有 JSON-RPC。日誌走 stderr。

## 掛到 Claude

先給 daemon 與 LLM 資料夾：

```sh
export AOS_DAEMON_DIR=/絕對路徑/aosd
export AOS_LLM_DIR=/絕對路徑/llm
claude mcp add aos -- python3 /絕對路徑/proto2/aos-mcp
```

如果 Claude 不是從同一個 shell 啟動，就在它的 MCP 設定裡給這兩個環境變數。
也可以在登記時一起存進去：

```sh
claude mcp add aos \
  -e AOS_DAEMON_DIR=/絕對路徑/aosd \
  -e AOS_LLM_DIR=/絕對路徑/llm \
  -- python3 /絕對路徑/proto2/aos-mcp
```

`AOS_DAEMON_DIR` 給 kernel 與 clock 工具用。
`AOS_LLM_DIR` 給 `llm_usage` 與 `llm_queue` 用。

世界路徑可以寫相對路徑。工具回的路徑一律是絕對路徑。
單次輸出超過 4000 字會截短。

## 工具

- `world_setup`：複製目前 git 版本的整個 `examples/`。要給 `dest`。可給 `engine`。它會回可玩的 agent 與 LLM 路徑。
- `kernel_status`：看 kernel 與全部時鐘。
- `kernel_start`：啟動 kernel。
- `kernel_stop`：停止 kernel。它也會停掉時鐘。
- `clock_register`：替 `world` 開鐘。可給 `interval` 秒。
- `clock_unregister`：關掉 `world` 的鐘。
- `clock_pause`：暫停 `world` 的鐘。
- `clock_continue`：讓 `world` 的鐘繼續。
- `agent_say`：給 `world` 與 `text`。把一句話送給 agent。
- `agent_listen`：等 `world` 的下一個回覆。`timeout_s` 預設 60 秒。
- `agent_status`：看 agent 的格數、用量與資料夾大小。
- `agent_spawn`：給 `world`、`name`、`persona`。`clock` 可選 `shared` 或 `own`。也可給 `template`。
- `agent_inbox_drop`：給 `world`、`source`、`content`。直接放一封 JSON 信。
- `llm_usage`：看今天用量。可給 `day`，格式是 `YYYY-MM-DD`。
- `llm_queue`：看執行中與排隊中的 LLM 請求。

先用 `world_setup`。它會回 `agent` 與 `llm` 的絕對路徑。
把 `AOS_LLM_DIR` 指到回傳的 `llm`。
接著啟動 kernel，再替 `agent` 與 `llm` 各開一個鐘。

## 錯誤

工具失敗會回 `isError: true`。
錯誤文字直接說是哪個參數或哪支 CLI 失敗。
`agent_listen` 等不到不是錯誤。它會回「還沒有新回覆」。

不認得的 JSON-RPC 方法回 `Method not found`。
