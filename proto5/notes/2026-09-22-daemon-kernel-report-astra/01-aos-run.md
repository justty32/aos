← [daemon／kernel 調查報告（astra）](../2026-09-22-daemon-kernel-report-astra.md)（分檔 1/6）｜[下一份](02-aos-daemon.md)

**1. aos-run**

**1.1 命令列、預設與驗證**

```text
aos-run xxx
  [--dir-target REL]
  [--timeout-ms N]
  [--interval-ms N]
  [--from-start]
  [--max-runs N]
  [--time-limit-ms N]
  [--stop-exit CODE]...
  [--status-fd N]
  [--stop-on-error]
  [--stderr PATH|-]
  [-- ARG...]
```

| 參數／旗標 | 型別 | 預設 | 現在的行為 |
|---|---|---|---|
| `xxx` | 字串 | **必填** | 普通檔案、`.json` 路徑或資料夾；省略退出 2 |
| `--dir-target` | 字串 | `.aos/inst.json` | 資料夾目標裡要讀的指令檔；直接交給 aos-exec |
| `--timeout-ms` | 整數 | `0` | 每次執行的 timeout；0 不限；負數退出 2 |
| `--interval-ms` | 整數 | `1000` | 相鄰兩次執行的間隔；允許 0；負數退出 2 |
| `--from-start` | 布林旗標 | `false` | 下一次時間從本次開始算；未給則從完成後算 |
| `--max-runs` | 整數 | `0` | 0 不限；正數為最多完成幾次 `run_target()`；失敗嘗試也計數 |
| `--time-limit-ms` | 整數 | `0` | 整個 loop 的時限；0 不限；負數退出 2 |
| `--stop-exit` | 可重複整數 | 空集合 | 回報碼命中任一值就停；負數退出 2，未限制上限 255 |
| `--status-fd` | 整數 | 不寫事件 | 往既有 fd 寫事件；只拒絕負數，不預先確認 fd 可寫 |
| `--stop-on-error` | 布林旗標 | `false` | 只有 `kind=aos` 才因此停止；`child` 非零與 `usage` 不算 |
| `--stderr` | 字串 | `None` | 覆蓋子程式 stderr；`-` 沿用 aos-run stderr；路徑相對於 **aos-run 自己的 cwd** |
| `--` | 分隔符 | 無 | 後面原樣當普通檔案的 argv；對 `.json`／資料夾，即使後面空白也退出 2 |
| `-h`／`--help` | 旗標 | 無 | argparse help，退出 0 |

起跑前只檢查：

1. 上述負值。
2. `xxx` 不存在且不是 `.json` 結尾：退出 2。
3. inst 類目標卻給 `--`：退出 2。

資料夾存在但裡面沒有指令檔，**沒有在 loop 外拒絕**；每次 `run_target()` 會回 `(2,"usage")`，預設仍一直重試。

來源：[aos_run.py:155](../../../proto4-3/aos_run.py)、[aos_exec.py:62](../../../proto4-3/aos_exec.py)。

**1.2 每一格實際做什麼**

| 次序 | 行為 |
|---|---|
| loop 初始化 | 建立訊號狀態，安裝 SIGTERM／SIGINT handler，寫 `ready`；以 `time.monotonic()` 記開始與 deadline |
| 第一次 | 不先等 interval，立即開始 |
| 等待 | 每次最多睡 0.05 秒；先看停止訊號，再看整體 deadline，再看下一次時間 |
| 算本次 timeout | 沒整體期限時沿用 `timeout_ms`；有期限則用「原 timeout 與剩餘整數毫秒的較小值」；原 timeout=0 視為不限 |
| 剩不到 1ms | 不開新的一次，直接以 `time_limit` 停止 |
| 開始 | 寫 `start #n` |
| 執行 | 呼叫 `aos_exec.run_target()`；每次重新辨識目標、重新讀 inst，不缓存已解析指令 |
| 正規化結果 | `kind=aos` 的 library code `1` 改成回報碼 `125`；其餘原樣 |
| 計數與回報 | `n += 1`；stderr 印一行；status fd 寫一行 `done` |
| 判斷停止 | 依序：訊號 → `stop_on_error` → `stop_exit` → `max_runs` → 整體 deadline |
| 排下一次 | `from_start`：本次開始＋interval；否則：此時的 monotonic 時間＋interval |
| 結束 | 印／寫 `stop <reason>`；還原原訊號 handler；關閉提供的 status fd |

`--from-start` 超時不補格，下一次直接開始；不是「最初起點＋n×interval」的固定時槽。

「整體時限」實作是縮短本次 subprocess timeout，**不是涵蓋所有讀檔、解析、開串流與清理的絕對截止保證**；TERM 後還可能等 2 秒才 KILL。

來源：[aos_run.py:65](../../../proto4-3/aos_run.py)、[aos_run.py:126](../../../proto4-3/aos_run.py)、[aos_exec.py:181](../../../proto4-3/aos_exec.py)。

**1.3 退出碼：本次執行與 aos-run 本身分開**

| 層次 | 碼／kind | 意思 |
|---|---|---|
| 本次執行 | `child`＋子程式碼 | 子程式正常結束；非零不自動停止 loop |
| 本次執行 | `child`＋`126` | 無執行權或其他啟動子程式的 OSError |
| 本次執行 | `child`＋`127` | 找不到程式／相關路徑不是目錄 |
| 本次執行 | `child`＋`128+N` | 子程式被訊號 N 結束 |
| 本次執行 | `aos`＋回報 `125` | 解析、前置處理等執行器錯誤；也包括子程式已完成但 exit 檔寫失敗 |
| 本次執行 | `usage`＋`2` | 本次目標不合法，例如指令檔消失 |
| aos-run 本身 | `0` | `max_runs`、`time_limit`、`stop_exit`、第一次停止訊號 |
| aos-run 本身 | `125` | `--stop-on-error` 命中 `kind=aos` |
| aos-run 本身 | `128+N` | 第二次同種 SIGTERM／SIGINT 觸發強制停止 |
| aos-run 本身 | `2` | CLI 用法錯；不是 loop 內每次 `usage` 的直接傳遞 |

因此：

- 子程式退出 100／101，**aos-run 沒有內建特殊解讀**。
- `--stop-exit 125` 同時可命中執行器失敗及子程式真的退 125。
- `--stop-on-error` 不會因子程式真的退 125 而停。
- 同次命中多個停止條件，以前表所列順序決定 reason。
- 未捕捉的 Python 例外不屬於上述正常退出協議。

來源：[aos_run.py:88](../../../proto4-3/aos_run.py)、[aos_run.py:113](../../../proto4-3/aos_run.py)、[aos_exec.py:226](../../../proto4-3/aos_exec.py)。

**1.4 訊號**

| 情況 | 實際動作 |
|---|---|
| 第一次 SIGTERM／SIGINT | 記 `stop=true`；正在跑的那次繼續完成；睡眠中則下次檢查就退 |
| 同一訊號第二次 | 記 `forced=true`；SIGKILL 正在執行之子程式的 process group |
| SIGTERM 一次、SIGINT 一次 | 分別計數，不等同同種訊號第二次 |
| 被強制結束的子程式 | 通常回報 `exit=137 kind=child` |
| 強制停止的 aos-run | 收到兩次 TERM 時通常退出 143；兩次 INT 時通常退出 130 |
| library 在非主執行緒用預設 handler 安裝 | 安裝失敗被吞掉，仍會發 `ready`；CLI 正常在主執行緒不走此情況 |

嚴格說，強制退出使用的是 `_State.signum`，而它會被**每一次後續訊號**更新；不是另外保存「首次觸發 forced 的訊號」。

來源：[aos_run_status.py:8](../../../proto4-3/aos_run_status.py)、[aos_run_status.py:59](../../../proto4-3/aos_run_status.py)。

**1.5 狀態檔與事件格式**

**aos-run 沒有自己的家目錄、`state.json`、`last.json`、`runs.jsonl` 或持久化執行次數。** 重新開一支，編號從 1 開始。

| 輸出 | 路徑／載體 | 格式、欄位、誰寫誰讀 |
|---|---|---|
| 人類紀錄 | 自己的 stderr | aos-run 寫 `aos-run: #<n> exit=<code> <seconds>s`；秒數一位小數 |
| 停止紀錄 | 自己的 stderr | `aos-run: stop <reason>` |
| 程式事件 | `--status-fd N` 指定 fd | UTF-8、每事件一行、尾端 `\n`；aos-run 寫，daemon status thread 讀 |
| inst 指定的 stdout／stderr | inst 或 CLI 指定路徑 | 由 aos-exec 開啟，內容由本次子程式輸出 |
| inst 指定的 exit | 解析後 `exit` 路徑 | aos-exec 寫十進位結束碼＋換行；可 append；fsync 檔案與父目錄 |

| status 事件 | 全部欄位 | 型別／意思 |
|---|---|---|
| `ready` | 只有事件名稱 | handler 安裝程序已走完，第一次尚未開始 |
| `start #n` | `n` | 十進位整數，本次編號 |
| `done #n exit=C kind=K T.s` | `n`、`C`、`K`、時間 | 整數、整數、`child/aos/usage` 字串、秒數一位小數 |
| `stop REASON` | `REASON` | `max_runs/time_limit/stop_exit/error/signal/signal_forced` |

事件用 `os.write()`，OSError 被忽略；没有非阻塞設定、重送、回執或落盤。結束時會關掉該 fd。

來源：[aos_run_status.py:32](../../../proto4-3/aos_run_status.py)、[aos_exec.py:242](../../../proto4-3/aos_exec.py)。

既有測試覆蓋：執行次數、間隔兩算法、timeout、整體時限、訊號、argv 分隔符、事件順序與 `stop-on-error`。見 [test_run.py:58](../../../proto4-3/test/test_run.py)、[test_run_status.py:36](../../../proto4-3/test/test_run_status.py)。

---

