← [入口](../proto8.md)｜涵蓋：`proto8/impls/` 的 `aos-llm-kernel`、`aos-llm-send`、`aos-json`｜上一份：[01-impls-2](01-impls-2.md)

行為細節以各專案 README 為準。路徑相對於該段標題的資料夾。建置檔見 [01-impls](01-impls.md) 的共通段。

## `impls/aos-llm-kernel/`（LLM kernel：排隊、額度、代跑單子）

| 檔 | 負責什麼 |
|---|---|
| `include/aos/llm_kernel.hpp` | 公開標頭（aos-llm-send 連它）：信箱、信、優先序、代號 |
| `src/letter/letter.cpp` | 信箱四格、寄信人存活（`sender.flock`）、`parse_priority`、`priority_of`、`read_reply` |
| `src/queue/queue.cpp`、`src/queue/queue.hpp` | `queue.json` 讀寫、`effective`、`order`（級數 → deadline → `time_ms` → 等得久 → 先寄） |
| `src/serve/serve.cpp`、`src/serve/serve.hpp` | `Server`：讀設定（`slots`、`budget`、`accept`）、`recover`、`sweep`、`scan`、`start_runner`、`wait_runners`、`finish`（`served.jsonl`、`used.json`）、回信 `post_reply`／`regret_reply`（撤回沒人拿的回信，aos-post 的 `regret`） |
| `src/budget/budget.cpp`、`src/budget/budget.hpp` | token 回報與額度：`parse_budget`、`window_since`、`read_used`／`add_used`、`spent`、`read_report` |
| `src/main.cpp` | 命令列 `aos-llm-kernel [旗標] kernel.json`（要 `AOS_STACK`） |
| `src/common/common.hpp` | 內部共用標頭 |

## `impls/aos-llm-send/`（閘門：寄單子給 kernel、等回信）

| 檔 | 負責什麼 |
|---|---|
| `src/send/send.cpp`、`src/send/send.hpp` | `mailbox`（`$AOS_KERNEL`）、`post`（寄信人身分用 aos-util 的 `identity`、解指示詞、驗 priority、信封〔沒有 `kind`〕、先鎖 `sender.flock` 再寫信、回信信箱 `reply_to`） |
| `src/wait/wait.cpp`、`src/wait/wait.hpp` | `wait_reply`（看回信信箱、訊號＝撤信）、`relay`（stdout／stderr 原樣、結束碼） |
| `src/main.cpp` | 命令列 `aos-llm-send [旗標] 單子.json` |
| `src/common/common.hpp` | 內部標頭：`reply_box` |

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
| `tools/json_edit/_entry`、`tools/json_edit/_tooldef.json` | 腦用工具：自己問腦，peek 找指標 → 問新值 → `batch` 一次寫 |
