# daemon 協議

← [整理區](../../README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[daemon](../../daemon/README.md)｜[慣例](../../conventions.md)｜[暫緩區的舊協議](../../deferred/protocol/daemon/README.md)

daemon 協議只定格式：`aos-daemon` 的 argv、設定檔欄位、輸出與結束碼，控制模組的 socket 訊息、環境變數與 `aos-ctl`。行為寫在 [daemon 正本](../../daemon/README.md)。

| 條號 | 標題 | 檔案 |
|---|---|---|
| P-100 | 範圍 | [README.md](README.md) |
| P-120 | aos-daemon 的 argv、設定檔、輸出與結束碼 | [core.md](core.md) |
| P-121 | 控制 socket、環境變數與 aos-ctl | [control.md](control.md) |

2026-10-01 之前的舊協議（P-101～119：舊設定檔、IPC 封包、登記與查詢 method、runner、helper 私有通道、停機與 `state.json`、tick–daemon 通道）第一版都不做，在[暫緩區](../../deferred/protocol/daemon/README.md)，條號保留、不重用。

## P-100．範圍〔使用者方向 2026-10-01〕

本篇只定格式：

- 核心 `aos-daemon`：argv、設定檔欄位（指示詞展開後的樣子）、stdout／stderr 的行格式、結束碼（P-120）；
- 控制模組：socket 上一行 JSON 的請求與回應、錯誤代碼、往下傳的環境變數、`aos-ctl` 的 argv、輸出與結束碼（P-121）。

行為一律以 [daemon 正本](../../daemon/README.md)（[B-640](../../daemon/core.md)、[B-641](../../daemon/control.md)）為準；這裡寫到行為時只留一句加條號（[P-001](../../../protocol/README.md)）。結束碼照 [C-08](../../conventions.md)，環境變數總表見 [C-10](../../conventions.md)。

### 共用約定哪些不適用 P-120／P-121〔astra 報告必修 3〕

[共用約定](../../../protocol/README.md)（P-001～007）是照舊 daemon 寫的。下表列出的那幾條**不適用** P-120／P-121，一律以 P-120／P-121 為準；表上沒列的（UTF-8 一行一個 JSON、不經 shell、`AOS_` 開頭、時間單位照 [C-01](../../../contracts.md) 等）照用。

| 共用條文 | 舊說法 | P-120／P-121 實際 |
|---|---|---|
| P-001「請求路線」、P-004 第 1 種載體 | 找 daemon＝socket 上的 JSON-RPC 2.0（`jsonrpc`、`id`、`method`、`params`），單行上限 256 KiB；另有 tick–daemon 通道 | 控制 socket 一條連線一問一答，請求是 `{"<指令>":"<inst>",…}`，不是 JSON-RPC、沒有 `id`；只限 1 秒內送完一行，沒有另訂大小上限；沒有通道 |
| P-002「持久 JSON 帶 `version`」、ID 格式 | 自己的持久檔帶 `"version": 1`；ID 照 `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` | 設定檔沒有 `version`（有了也當陌生欄位忽略）；`insts` 的鍵是 inst 字面值，任何字串，不套 ID 格式 |
| P-002、[C-07](../../../contracts.md)「daemon IPC 拒絕陌生欄位」 | daemon IPC 嚴格 | 設定檔、控制請求都照收不理（P-120、P-121） |
| P-004「核對身分」 | 看 `SO_PEERCRED`，通道上看憑證 | 不驗身分，連得上就能用；憑證現行控制不使用（舊通道憑證暫緩） |
| P-005 錯誤 | JSON-RPC `error`、-32000 加 `data.code`、`retryable` | `{"ok":false,"error":"<代碼>","detail":"<字串>"}`，代碼只有 P-121 那三個 |
| P-006 結束碼、程式名、通道變數 | `2`＝用法錯、`125`＝無法開始；程式叫 `aos daemon`；`AOS_DAEMON_SOCKET`＋`AOS_TICK_TOKEN` 是通道變數 | 照 [C-08](../../conventions.md)：只有 0 與 1，用法錯回 1；程式叫 `aos-daemon`、`aos-ctl`；`AOS_DAEMON_SOCKET` 是控制 socket，另配 `AOS_DAEMON_INST` |
| P-007 放寬表 | 列的是舊 schema（`daemon-rpc` 嚴格、`daemon-config` 放寬） | `daemon-core-config`、`daemon-ctl` 的請求都放寬；請求與回應分開驗（P-121） |

依據：使用者方向 2026-10-01（最核心 daemon、控制模組）；原本的範圍（設定、IPC method、通道、helper 私有通道、runner）定於使用者方向 2026-09-29、第十八批、第十九批，隨舊協議搬到暫緩區。
