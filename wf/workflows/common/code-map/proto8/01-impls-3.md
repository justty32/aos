← [入口](../proto8.md)｜涵蓋：`proto8/impls/` 的 `aos-llm-kernel`、`aos-llm`、`aos-json`｜上一份：[01-impls-2](01-impls-2.md)

行為細節以各專案 README 為準。路徑相對於該段標題的資料夾。建置檔見 [01-impls](01-impls.md) 的共通段。

## `impls/aos-llm-kernel/`（LLM kernel：排隊、額度、請 daemon 掛問腦 proc 跑自己的 endpoint 函數）

| 檔 | 負責什麼 |
|---|---|
| `include/aos/llm_kernel.hpp` | 公開標頭（aos-llm 連它）：信箱、信（`body.endpoint`／`request`／`priority`）、優先序、回信形狀、代號（含 `Endpoint*`、`RequestBad`、`DaemonMissing`） |
| `src/daemon/daemon.cpp`、`src/daemon/daemon.hpp` | 跟 daemon 說話（11-05）：`find_host`（要 `AOS_DAEMON`；掛信寄 `AOS_KERNEL`，沒設＝daemon 的 ctl 信箱）、`read_table`（`procs_state.json` 的 `procs`、`mailbox_warning`）、`send_procs`（寄 `procs_*` 信，aos-post） |
| `src/letter/letter.cpp` | 信箱三格（`tmp`／`new`／`cur`）、寄信人存活（`sender.flock`：`has_sender`／`sender_alive`）、`parse_priority`、`priority_of`（`body.priority`）、`reply_of`／`read_reply`（`{"message"}` 或 `{"error"}`） |
| `src/queue/queue.cpp`、`src/queue/queue.hpp` | `queue.json` 讀寫、`effective`、`order`（級數 → deadline → 等得久 → 先寄） |
| `src/serve/serve.cpp`、`src/serve/serve.hpp` | `read_cfg`（`slots`、`budget`、`exec`、`endpoints`、`endpoint`、`timeout_ms`；信箱固定 `$AOS_STACK/mailbox`）；`Server`：`collect`＋`settle`（看 daemon 的表與 `<信>/state.json` 收成品：結束碼 0＋`reply.json`＝回信、其他＝`EndpointFailed`、逾時、被收掉／死在半路重掛一次、`stopped` 列順手拔）、`sweep`（只看有 `sender.flock` 的信）、`scan`＋`pick`（查代號、解那組、定 exec）、補位到 `slots`＋`mount`（寫 `request.json`、寄掛信 `llm_<信件名稱>`〔`max: 1` 的 loop 型、stack＝信資料夾〕、寫 `proc.json`；寄不進＝`LaunchFailed`）、`finish`（寄回信〔寄不出去＝stderr 一行〕、`used.json`、整封刪掉）、回信 `post_reply`／`regret_reply`（`reply_to` 經 aos-post 的 `reply_to_abs` 從信箱根拼回，11-05；寄完時同步寄信的人已不在＝撤回沒人拿的回信，aos-post 的 `regret`） |
| `src/budget/budget.cpp`、`src/budget/budget.hpp` | token 與額度：`parse_budget`、`window_since`、`read_used`／`add_used`、`spent`、`report_of`（回信的 `usage`） |
| `src/main.cpp` | 命令列 `aos-llm-kernel [旗標] kernel.json`（要 `AOS_STACK`；`AOS_DAEMON` 由 serve 要） |
| `src/common/common.hpp` | 內部共用標頭 |

## `impls/aos-llm/`（基礎工具：寄請求信給 kernel、收回信；11-04 由 aos-llm-send 改名）

| 檔 | 負責什麼 |
|---|---|
| `src/send/send.cpp`、`src/send/send.hpp` | `kernel`（`$AOS_LLM_KERNEL`＝llm kernel 的 stack，信箱 `<stack>/mailbox`；相對的有 `AOS_DAEMON`＝相對它、沒有＝相對 cwd；沒設＝`LlmKernelMissing`）、`read_body`（stdin 整份 body、`--priority` 蓋上、驗形狀與 priority）、`send`（非同步：aos-post 的 `init`／`send`，不建 `sender.flock`）、`send_held`（同步：先鎖 `sender.flock` 再寫信、回信信箱 `<信箱>/reply/`）、`regret`（aos-post 的 `regret`） |
| `src/wait/wait.cpp`、`src/wait/wait.hpp` | `recv`（照 `in_reply_to` 找回信、印 `body.message`；沒到 10）、`ask_wait`（20 ms 輪詢、訊號＝撤信）；內部 `find_reply`、`take`、`deliver`、`withdraw` |
| `src/main.cpp` | 命令列 `aos-llm send [--priority P] --reply-to BOX`／`recv BOX 名`／`ask [--priority P]`／`regret 名` |
| `src/common/common.hpp` | 內部標頭：`reply_box`、代號（加 `RegretFailed`） |

## `impls/aos-json/`（讀、改 aos 的 JSON 設定；沒有公開標頭）

| 檔 | 負責什麼 |
|---|---|
| `src/main.cpp` | 命令列 `aos-json 子命令 [旗標] 檔#/指標`：`get`、`peek`、`where`、`set`、`batch`、`del`、`append`、`merge`、`env`、`ref`、`check` |
| `src/common/common.hpp` | 自己的錯誤代號 |
| `src/doc/doc.hpp` | `File`、`Docs`、`Spec`、指標 |
| `src/doc/file.cpp` | `load_file`（記 `#!`、縮排、權限）、`save_file`（原子寫、值沒變不寫） |
| `src/doc/splice.cpp` | 寫回只重寫有變的那塊，其他原文不動 |
| `src/doc/pointer.cpp` | `檔#/指標` 拆開、RFC 6901 指標 |
| `src/follow/follow.hpp` | `Kind`、`Cursor`、`Mode`、`Located` |
| `src/follow/kind.cpp` | 認指示詞（寬容規則同 aos-directive） |
| `src/follow/locate.cpp` | `locate`：往下走、`--follow` 穿 `$ref`；**跟 aos-directive 的規則要一起改** |
| `src/cmd/cmd.hpp` | 每個子命令一個函數、`problems_of` |
| `src/cmd/read.cpp` | `get`、`where` |
| `src/cmd/peek.cpp` | `peek`：漸進展開 |
| `src/cmd/write.cpp` | `set`、`batch`、`del`、`append`、`merge`、`env`、`ref`；共用 `Edit`（`--check` 比原本多出問題才擋） |
| `src/cmd/check.cpp` | `check`：`$ref` 指得到、指示詞寫法、`exec` 形狀 |
| `tools/json/_entry`、`tools/json/_tooldef.json` | 腦用工具：一次一個 aos-json 動作 |
| `tools/json_edit/_entry`、`tools/json_edit/_tooldef.json` | 腦用工具：自己問腦（`aos-llm ask`，11-04 晚），peek 找指標 → 問新值 → `batch` 一次寫 |
