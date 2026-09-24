本報告以 **2026-09-22 調查時的工作樹**為準；調查開始時 HEAD 為 `9c45f06cd6ac4bd6c2e24f66cf724952dd2dfe92`。全程未修改檔案。已逐支閱讀指定程式與相關測試；**沒有執行會建立檔案、啟動 daemon 或 worker 的測試**。另外用記憶體中的 JSON 與 mock 讀檔核對了部分解析差異。

以下以程式碼為事實來源，測試作為既有行為的旁證。「型別」若沒有另註，是程式正常寫出的型別，**不表示讀取端有完整驗證該型別**。

| 本報告用語 | 意思 |
|---|---|
| `H` | daemon 家目錄 |
| `K` | kernel 家目錄 |
| CPU | daemon 管理的一支 `aos-run`；反覆讀取同一路徑的指令檔 |
| kernel 行程／`pid` | kernel 的邏輯行程，名稱是字串，來自 `<pid>.json` 的檔名；不是 Linux PID |
| daemon entry 的 `pid` | `aos-run` 的 Linux PID，整數 |
| 一次執行 | 一次 `aos_exec.run_target()` |
| kernel tick | 一次 `aos-kernel-tick`；與 CPU 完成一次執行不是同一件事 |
| `kind` | `child`、`aos`、`usage`，用來區分退出碼來源 |

---

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

來源：[aos_run.py:155](../../proto4-3/aos_run.py)、[aos_exec.py:62](../../proto4-3/aos_exec.py)。

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

來源：[aos_run.py:65](../../proto4-3/aos_run.py)、[aos_run.py:126](../../proto4-3/aos_run.py)、[aos_exec.py:181](../../proto4-3/aos_exec.py)。

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

來源：[aos_run.py:88](../../proto4-3/aos_run.py)、[aos_run.py:113](../../proto4-3/aos_run.py)、[aos_exec.py:226](../../proto4-3/aos_exec.py)。

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

來源：[aos_run_status.py:8](../../proto4-3/aos_run_status.py)、[aos_run_status.py:59](../../proto4-3/aos_run_status.py)。

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

來源：[aos_run_status.py:32](../../proto4-3/aos_run_status.py)、[aos_exec.py:242](../../proto4-3/aos_exec.py)。

既有測試覆蓋：執行次數、間隔兩算法、timeout、整體時限、訊號、argv 分隔符、事件順序與 `stop-on-error`。見 [test_run.py:58](../../proto4-3/test/test_run.py)、[test_run_status.py:36](../../proto4-3/test/test_run_status.py)。

---

**2. aos-daemon／aos-daemon-ctl**

**2.1 家目錄選擇**

| 項目 | 實際行為 |
|---|---|
| 優先序 | 非空 `--home H` → 非空 `AOS_DAEMON_HOME` → `~/.aos-daemon` |
| 正規化 | `Home` 使用 `os.path.abspath()`，不是 realpath |
| `~` 展開 | 預設值在模組載入時 `expanduser()`；explicit/env 值本身沒有額外 expanduser |
| 相對路徑 | 相對於各程序自己的 cwd；daemon 不會 chdir 到 H |
| 環境傳遞 | `--home` 不會設定 `AOS_DAEMON_HOME`，也不會自動傳給 kernel 子孫 |
| 存活判斷 | 讀 `daemon.pid`，檢查 `/proc/<pid>/stat` 存在且不是 `Z` |
| PID 身分 | 不確認該 PID 是不是同一支 daemon，不核對開始時間 |
| 鎖 | 沒有家目錄鎖或原子 PID 排他建立 |

來源：[aos_home.py:20](../../proto4-3/aos_home.py)、[aos-daemon:36](../../proto4-3/aos-daemon)。

**2.2 家目錄完整清單**

| 路徑 | 格式／初值 | 誰寫／誰讀 | rename／刪除時機 |
|---|---|---|---|
| `H/` | 資料夾 | daemon 啟動、`put_request()` 建立 | 不自動刪 |
| `H/requests/` | 請求資料夾 | ctl／外部寫；daemon 掃描 | 不自動刪資料夾 |
| `H/requests/<name>.json` | 請求 JSON | ctl／外部寫；daemon 讀 | handler 執行後先刪原檔，再寫 done 回應 |
| `H/requests/<name>.json.tmp` | 尚未發佈的請求 | `put_request()` 經共用 writer 寫 | 寫完 `os.replace()` 成 `.json`；daemon 不掃 `.tmp` |
| `H/requests/done/` | 回應資料夾 | daemon 建立／寫；ctl／外部讀 | 不自動清理 |
| `H/requests/done/<name>.json` | 原請求＋`ok`＋`result`；壞輸入例外見後表 | daemon 寫；ctl 讀 | ctl 讀後**不刪**；沒有保存上限 |
| `H/requests/done/<name>.json.tmp` | 回應暫存 | daemon 寫 | replace 到正式回應 |
| `H/daemon.pid` | 十進位 PID 純文字，**沒有換行** | `serve()` 覆寫；ctl、啟動檢查讀 | 正常 shutdown 刪；不是暫存＋rename |
| `H/state.json` | 狀態 JSON，初始 `runs={}` | daemon 寫；ctl、kernel 讀 | `state.json.tmp`→replace；正常 shutdown 刪 |
| `H/state.json.tmp` | 狀態暫存 | daemon 寫 | replace；沒有通用殘留暫存清理程序 |
| `H/daemon.log` | UTF-8 文字 append | daemon 主線與各 stderr thread 寫；人讀 | 不輪替、不自動刪 |

共用 `write_json()`：先建父目錄，UTF-8、`ensure_ascii=False`、`indent=1`，寫 `<path>.tmp` 再 `os.replace()`。**沒有 fsync 檔案或父目錄，也沒有多 writer 鎖。**

ctl 請求檔名為：

```text
<Unix時間毫秒，至少13位>-<ctl的Linux PID>.json
```

同一 PID 在同一毫秒投多張可能同名；不是 UUID 或排他建立。

來源：[aos_home.py:28](../../proto4-3/aos_home.py)、[aos_home.py:59](../../proto4-3/aos_home.py)、[aos_daemon_req.py:56](../../proto4-3/aos_daemon_req.py)、[aos_daemon_lifecycle.py:19](../../proto4-3/aos_daemon_lifecycle.py)。

**2.3 `H/state.json` 全欄位**

頂層：

| 欄位 | 型別 | 初值／來源 | 寫入者／讀取者 |
|---|---|---|---|
| `pid` | 整數 | daemon 的 `os.getpid()` | daemon／ctl、kernel status |
| `home` | 字串 | H 的絕對路徑 | daemon／外部讀者 |
| `runs` | 物件 | `{}`；key＝target 的 realpath | daemon／ctl、kernel |

`runs[<key>]` 的完整 entry：

| 欄位 | 型別 | 初值 | 更新／意思 |
|---|---|---|---|
| `pid` | 整數 | `Popen.pid` | 這支 aos-run 的 Linux PID |
| `target` | 字串 | target 的 abspath | 保留 symlink 路徑，不等同 key 的 realpath；restart 可更新 |
| `args` | 字串陣列 | 提交 args 逐項 `str()` | 不含 daemon 自動追加的 `--status-fd` |
| `started_at` | number | `time.time()` | 開立 entry 時的 Unix 秒 |
| `state` | 字串 | `"running"` | 五態狀態機，見下表 |
| `ready` | 布林 | `false` | 收到 `ready` 後為 true，不再清回 false |
| `running` | 布林 | `false` | 收到 `start`→true；收到 `done`→false |
| `runs` | 整數 | `0` | 最近 `done #n` 的 n，不是 start 次數 |
| `last_exit` | 整數或 null | `null` | 最近 done 的 exit |
| `last_kind` | 字串或 null | `null` | 最近 done 的 kind；parser 不限制允許字串集合 |
| `last_line` | 字串或 null | `null` | 最近 status 原文；包括 stop 或看不懂的行 |
| `alive` | 布林 | 動態計算 | `Popen.poll() is None`；不是從 status 事件推算 |

`start` **不清掉**前一次 `last_exit/last_kind`。duration 沒有獨立 JSON 欄位，只留在 `last_line` 文字內。

另有只存在 daemon 記憶體、不寫 state 的欄位：

| 欄位 | 初值／用途 |
|---|---|
| `stop_deadline` | `None`；停止後設 monotonic＋5 秒 |
| `force_at` | `None`；force 的第二發 TERM 時間 |
| `new_args` | `None`；restart 後下一支的 args |
| `proc` | Popen 物件 |
| `status_fd` | status pipe 讀端 fd |
| `thread`、`sthread` | stderr／status 讀取 thread |
| `key` | table key |

來源：[aos_daemon_entry.py:67](../../proto4-3/aos_daemon_entry.py)、[aos_daemon_entry.py:94](../../proto4-3/aos_daemon_entry.py)、[aos_daemon_lifecycle.py:15](../../proto4-3/aos_daemon_lifecycle.py)。

**2.4 key 與接受的目標**

| 項目 | 行為 |
|---|---|
| key | `realpath(abspath(target))` |
| target | 執行時使用 `abspath(target)`，不強制改成 key |
| add／restart | 拒絕資料夾；要求提交路徑 `.json` 結尾；不要求檔案存在，不驗 inst 內容 |
| rm／get／pause／resume | 不驗副檔名，只正規化成 key 查表 |
| 同 key 再 add | `ok:false`，原 entry 不動 |
| 同目錄多個 `.json` | 各自一支 aos-run |
| 指令檔更新 | aos-run 下一次重新讀取 |
| symlink 改指向 | entry 的既有 key 不會自動跟著變；aos-run 仍沿 target 路徑讀。之後用該 symlink 查表會重新算 realpath |

來源：[aos_daemon_entry.py:40](../../proto4-3/aos_daemon_entry.py)、[aos_daemon.py:51](../../proto4-3/aos_daemon.py)。

**2.5 請求檔協議**

常規請求欄位：

| 欄位 | 常規型別 | 預設／實際驗證 |
|---|---|---|
| `op` | 字串 | 沒有預設；缺少時以不認得的 `None` 回拒絕 |
| `target` | 路徑字串 | 有目標的 op 必填；沒有獨立型別驗證 |
| `args` | 字串陣列 | add/restart 省略或 falsy 值→`[]`；逐項 `str()`，沒有先確認是陣列 |
| `force` | 布林 | remove 省略→false；實際使用 `bool(value)` |
| 其他欄位 | 任意 JSON | 不參與操作；若原請求是物件，會保留進 done |

例如 `args` 是字串時會逐字元當參數；`force:"false"` 因非空字串而被當成 true。這是目前轉型行為。

| `op` | 需要欄位 | 立即回應的 `result` | 後續動作 |
|---|---|---|---|
| `add` | `target`；可選 `args` | 新 entry 物件 | 開 aos-run；**不等 ready，也不確認第一格成功** |
| `remove` | `target`；可選 `force` | `"stopping"` | 進停止流程 |
| `restart` | `target`；可選 `args` | `"restarting"` | 舊 runner 退出後，以新 args 開新 runner |
| `get` | `target` | 一個 entry 物件 | 無 |
| `ls` | 無 | key→entry 物件 | 無 |
| `pause` | `target` | `"pause_pending"` 或 `"paused"` | 等可暫停條件 |
| `resume` | `target` | `"running"` | 取消 pending 或 CONT |
| `stop` | 無 | `"收工中"` | 設 daemon stopping，稍後 shutdown |

**請求共有八種 op。CLI 的 `rm` 會轉成協議的 `remove`；協議不認 `rm`。**

回應：

| 輸入情況 | done 內容 |
|---|---|
| 正常 JSON 物件 | 原物件全部欄位＋`ok:boolean`＋`result` |
| 物件原本有 `ok/result` | 被 daemon 的結果覆蓋 |
| 非物件或讀 JSON 失敗 | `{"req":"<請求檔名>","ok":false,"result":"<訊息>"}` |
| 操作拒絕 | `ok:false`，result 為中文訊息字串 |
| 讀取／dispatch 丟一般例外 | result 為 `"例外類別: 訊息"` |

處理順序：

1. 取 `requests/` 頂層 `.json` 普通檔案，按檔名字典序。
2. 讀取並 dispatch。
3. 不成功時 append 拒絕 log。
4. 嘗試刪原 request。
5. 成功操作先寫 state。
6. 另寫 `done/<同名>.json.tmp`，replace 成回應。

**done 代表該請求已處理／受理，不表示非同步狀態轉換已完成。** 沒有 `done:true`、完成時間、請求 ID 欄位或重試次數欄位；檔名就是關聯依據。

來源：[aos_daemon_req.py:28](../../proto4-3/aos_daemon_req.py)、[aos_daemon_req.py:56](../../proto4-3/aos_daemon_req.py)。

**2.6 五態與停止／重啟**

| 現態／事件 | 動作 | 新態 |
|---|---|---|
| add 成功 | 建 entry | `running`，即使還沒 ready |
| running＋pause | 只標記 | `pause_pending` |
| pause_pending，且 ready=true、running=false | 對 **aos-run PID** 送 SIGSTOP | `paused` |
| paused＋pause | 不再送訊號 | `paused` |
| pause_pending＋pause | 再標 pending | `pause_pending` |
| paused＋resume | 對 aos-run PID 送 SIGCONT | `running` |
| pause_pending＋resume | 取消 pending | `running` |
| running＋resume | 冪等 | `running` |
| stopping/restarting＋pause/resume | 拒絕 | 不變 |
| 一般狀態＋remove | 若 paused 先 CONT；送 TERM；deadline=現在＋5 秒 | `stopping` |
| remove force | 上述流程，再安排約 0.2 秒後第二發 TERM | `stopping` |
| stopping/restarting＋remove | 改 stopping；force 可安排立即補 TERM | `stopping`，取消重啟 |
| 一般狀態＋restart | 記新 target/args；送停止訊號 | `restarting` |
| stopping/restarting＋restart | 更新新 target/args；不重設既有停止 deadline | `restarting` |
| 到停止 deadline 仍活著 | KILL aos-run 的 process group | 等 reap |
| runner 自行退出 | reap 移除、寫 log | entry 消失 |
| restarting 的 runner 退出 | 移除舊 entry，再 add | 新 `running`；若新 add 失敗，沒有重試 |

pause 只停 aos-run，沒有停 inst 子程式的 process group。若 SIGSTOP 剛好落在新一次開始後，子程式仍可繼續跑，但 aos-run 暫時不能收結果或執行 timeout 邏輯。

來源：[aos_daemon.py:84](../../proto4-3/aos_daemon.py)、[aos_daemon_entry.py:118](../../proto4-3/aos_daemon_entry.py)。

**2.7 啟動、每輪、正常停止、崩潰**

| 階段 | 真正行为 |
|---|---|
| 啟動檢查 | ensure 家；若 `daemon.pid` 指向活 PID，退出 1 |
| 建 daemon | table 固定從 `{}` 開始；**不載入舊 state 恢復 entries** |
| serve 開始 | 覆寫 pid；安裝 TERM/INT handler；寫啟動 log；寫空 state |
| 每輪 | `handle_requests()` → `advance()` → `reap()` |
| 週期存檔 | 每輪工作後，距上次週期存檔至少 0.5 秒才存；不是固定 0.5 秒時鐘 |
| 輪間等待 | 本輪工作結束後再等約 0.2 秒，以 0.02 秒小步睡 |
| 額外立即存檔 | 成功請求、advance 有狀態變更訊息、reap |
| 背景讀取 | 每 entry 兩個 daemon thread：status 更新記憶體；stderr append log |
| reap | `poll()` 判死亡，移出 table；兩條 reader 各 `join(1.0)`；記退出碼、最後事件 |
| 收到 daemon TERM／INT | 只設 stopping；不是第二次訊號強制 kill 的機制 |
| 收到 stop 請求 | 設 stopping；同批尚未處理的請求仍會继续，這輪 advance/reap 也仍執行 |
| shutdown | 全部 CONT＋TERM；共同等至多 5 秒；剩餘 runner KILL group，各再 wait 最多 2 秒、join reader；清 table；刪 state/pid；留 log、requests、done |
| 正常退出碼 | 0 |
| 例外 | 主 loop 的 `finally` 會進 shutdown；但啟動前段或 shutdown 自己的未捕捉例外仍可能異常退出 |

**process group 的實際邊界：**

```text
daemon
  └─ aos-run：新 session / group
       └─ inst 子程式：aos-exec 再開另一個新 session / group
```

因此 daemon 五秒後的 `killpg(aos-run)` **不保證殺到 inst 子程式群組**。`rm --force` 的第二發 TERM 若被 aos-run handler 收到，則是 aos-run 主動 KILL 它記住的 child group；兩者不是同一條清理路徑。

來源：[aos_daemon_lifecycle.py:19](../../proto4-3/aos_daemon_lifecycle.py)、[aos_daemon.py:185](../../proto4-3/aos_daemon.py)、[aos_daemon_entry.py:166](../../proto4-3/aos_daemon_entry.py)、[aos_exec.py:190](../../proto4-3/aos_exec.py)。

| 崩潰後項目 | 現況 |
|---|---|
| SIGKILL 等未走 shutdown | pid、state 可殘留 |
| 舊 aos-run | 沒有 parent-death 自動清理設定；也沒有新 daemon 收養／對帳程序 |
| 舊 status pipe | 新 daemon 不會重新接上 |
| 新 daemon 啟動 | 舊 PID 不活就可起；空 table 覆寫舊 state |
| 未處理 requests | 新 daemon 會照常掃描處理 |
| 已刪 request、尚未寫 done | 沒有補償或重新產生回應機制 |
| 操作已執行、request 尚未刪時崩潰 | 重啟後可能再次處理同張檔；沒有通用去重交易 |
| state 原子 rename | 只保證讀者不讀到半份 JSON；不是持久化交易或恢復協議 |
| inst exit 檔 | aos-exec 有 fsync，但 daemon 不用它復原 table |
| PID 重用 | 可能把其他程序誤認成仍活著的 daemon |
| 同時啟動兩支 | 檢查 PID 與寫 PID 之間沒有鎖 |

**2.8 CLI 與等待**

```text
aos-daemon [--home H]

aos-daemon-ctl add FILE.json [aos-run flags...]
aos-daemon-ctl restart FILE.json [aos-run flags...]
aos-daemon-ctl rm FILE.json [--force]
aos-daemon-ctl get FILE.json
aos-daemon-ctl ls
aos-daemon-ctl pause FILE.json
aos-daemon-ctl resume FILE.json
aos-daemon-ctl stop
```

ctl 可在任何位置抽出第一個 `--home H` 或 `--home=H`。

| 命令 | 讀寫與等待 | 正常退出 |
|---|---|---|
| `aos-daemon` | 前台 serve，不自動背景化 | 正常停 0；活 PID 已存在 1；未知參數 2 |
| daemon `-h/--help` | 只有原 argv 第一項是 help 才直接顯示 | 0 |
| ctl `ls` | 直接讀 state，印整表，不投請求 | 有可讀 state 0；沒有 1 |
| ctl `get FILE` | 直接讀 state，只印該 key | 找到 0；找不到／無 state 1 |
| ctl `add` | 投單，等 done 至多 10 秒 | ok→0；拒絕／超時→1 |
| ctl `resume` | 同 add；不另等下一次 start | 0／1 |
| ctl `rm` | done 成功後，再等 key 從 state 消失，最多另 10 秒 | 到位 0；超時 1 |
| ctl `restart` | 先記舊 PID；done 後等新 PID≠舊 PID且 state=`running` | 到位 0；超時 1；**不要求 ready** |
| ctl `pause` | done 後等 state=`paused`，最多另 10 秒 | 到位 0；超時 1 |
| ctl `stop` | 投 stop，**不讀 done**；直接等原 daemon PID 消失，最多 10 秒 | 消失 0；仍活 1 |
| ctl 用法錯 | 無命令、未知命令、必要 target 缺少 | 2 |
| ctl `--help` | 沒有專門 help 分支，當未知命令 | 2 |

補充精確行為：

| 項目 | 現況 |
|---|---|
| daemon 不活 | 除 ls/get 外先拒絕，不投單 |
| daemon 不活但有 state | ls/get 仍可成功，stderr 提醒這是最後狀態 |
| `add/restart --dir-target` | ctl 明確拒絕，退出 2；直接寫 request 則沒有這道檢查 |
| 其他 run flags | ctl 不驗，交給新 aos-run；所以 **ctl add 成功不代表旗標合法** |
| `restart` 沒附 flags | 新 args=`[]`，不保留舊旗標 |
| 多餘參數 | ls/stop 忽略尾端參數；get/pause/resume 只用首個 target；rm 除 `--force` 外只用首個項目 |
| ctl 輪詢 | 每 0.05 秒；timeout 用 `time.time()`，不是 monotonic |
| 回應輸出 | `ask()` 先印 `ok=... result=...`，才進第二階段等待；到位後再印 removed/restarted/paused |
| 超時 | 不撤 daemon request，不取消已受理動作 |
| `--stderr REL` 經 ctl 傳入 | 相對於 daemon／aos-run 繼承的 cwd；不是 ctl 的 cwd，也不是 H 或 inst cwd |

來源：[aos_daemon_ctl.py:44](../../proto4-3/aos_daemon_ctl.py)、[aos_daemon_ctl.py:118](../../proto4-3/aos_daemon_ctl.py)、[aos_daemon_ctl.py:167](../../proto4-3/aos_daemon_ctl.py)。

**2.9 錯誤代號**

daemon／ctl **沒有自訂、穩定的具名錯誤代號欄位**。有的是 CLI 退出碼與 `result` 文字。

| 錯誤類別 | 回報方式 |
|---|---|
| 重複 add | `ok:false`；「已經有一個在跑」 |
| 不存在的 entry | `ok:false`；「沒有在跑」 |
| 非 `.json`／資料夾目標 | `ok:false`；「只收 .json 檔…」 |
| 停止中 pause/resume | `ok:false`；「正在收掉，不能…」 |
| 缺 target | `ok:false`；「缺欄位…」 |
| 未知 op | `ok:false`；「不認得的 op…」 |
| 非 JSON 物件 | `ok:false`；「請求不是一個 JSON 物件」 |
| 壞 JSON／其他 dispatch 例外 | `ok:false`；Python 例外類別名稱＋訊息 |
| Popen 開不起來 | `ok:false`；「開不起來…」 |
| ctl daemon 不活／等不到 | stderr 訊息，退出 1 |
| inst 解析失敗 | 不變成 daemon request 錯誤；透過 aos-run 的 `last_kind=aos,last_exit=125` 與 log 觀察 |

既有測試確認 key、十二個 entry 欄位、五態、force、restart、CLI 生命周期與正常停止清理。**沒有建立崩潰復原、請求交易、PID 重用或跨 session 子孫清理保證。** 見 [test_daemon.py:74](../../proto4-3/test/test_daemon.py)、[test_daemon_ops.py:14](../../proto4-3/test/test_daemon_ops.py)、[test_daemon_cli.py:98](../../proto4-3/test/test_daemon_cli.py)。

---

**3. aos-kernel**

**3.1 程式入口與命令列**

沒有 `aos-kernel status`、`aos-kernel module`、`aos-kernel syscall` 或 `aos-kernel schedule` 這些通用子命令；相關 Python 檔是內部實作。狀態命令是 `ls`，module 直接使用它的 `NAME` 當子命令。

| 命令 | 參數／旗標 | 成功 | 已處理失敗／用法錯 |
|---|---|---:|---|
| `aos-kernel-init DIR` | 必填 `--ncpu N`；其餘見 config 表；`--module PATH` 可重複 | 0 | DIR 已存在 1；解析／範圍錯 2 |
| `aos-kernel-boot K` | `--home H` 或 `--home=H` | 0 | 非家／缺 inst／daemon 不活／add 失敗 1；參數數量錯 2 |
| `aos-kernel-tick` | 不收任何參數；cwd=K | 0 | 非家 1；有參數 2 |
| `aos-kernel add [K] INST` | `--name NAME` | 0 | 家／檔案／inst／名稱／寫入錯 1；參數形狀錯 2 |
| `aos-kernel rm [K] NAME` | 無旗標，固定等回音 | 0 | 找不到／回音失敗／超時 1；參數或 NAME 錯 2 |
| `aos-kernel ls [K]` | 無旗標 | 0 | 非家／chdir 失敗 1；超過一個參數 2 |
| `aos-kernel <NAME> ...` | module CLI 自訂 | module 回碼 | hook 例外 1；找不到子命令通常 2 |
| `aos-kernel init/tick` | 舊子命令 | — | 2，提示使用獨立執行檔 |
| `aos-kernel -h/--help/help` | 頂層 help | 0 | — |
| `aos-kernel` 無參數 | — | — | 2 |

補充：

- init、add 把 argparse 的所有 `SystemExit` 都轉成 2，因此它們的 `--help` **印完 help 也回 2**。
- tick 的 `--help` 是「有參數」，回 2。
- boot 沒有專門 help 分支。
- 未知 module 命令若連 K 都不是有效家，先回 1，而不是最後的未知命令 2。
- tick/init 等仍有未捕捉的 filesystem／資料形狀例外；不能把表中的正常處理分支理解成完整防炸保證。

來源：[aos_kernel.py:151](../../proto4-3/aos_kernel.py)、[aos_kernel.py:198](../../proto4-3/aos_kernel.py)、[aos_kernel_init.py:24](../../proto4-3/aos_kernel_init.py)、[aos_kernel_tick.py:140](../../proto4-3/aos_kernel_tick.py)。

**3.2 家目錄逐檔**

| 路徑 | 格式／初值 | 誰寫／誰讀 | rename／刪除 |
|---|---|---|---|
| `K/` | `abspath(DIR)` | init 建；全部 kernel 工具用 | init 要求整個路徑不存在，不覆寫現有家 |
| `K/inst.json` | `{"argv":["<絕對路徑>/aos-kernel-tick"],"cwd":"."}` | init 寫；boot 查；daemon 的 aos-run 執行 | `.tmp`→replace；kernel 不定期改寫 |
| `K/config.json` | 後表八個欄位 | init 寫；各 kernel CLI、tick 讀 | `.tmp`→replace；後續修改只能由外部進行 |
| `K/state.json` | `cpus`、`queue`、`waiting` | init／tick 寫；tick/add/ls/rm 讀 | `.tmp`→replace |
| `K/kernel.log` | 純文字 append | init／tick 寫；ls、人讀 | 不輪替、不自動刪 |
| `K/procs/` | 就緒指令檔目錄 | init 建；add、scheduler 寫；tick 掃 | 不自動刪目錄 |
| `K/procs/<pid>.json` | inst JSON；未知欄位保留 | add 複製正規化後內容；scheduler 換下時 hard-link | 上 CPU 時 replace；壞檔 replace 到 bad；rm unlink |
| `K/procs/.<pid>.json.tmp` | add 暫存 inst | add 寫、驗 | 驗過才 replace；失敗嘗試刪 |
| `K/procs/bad/<pid>.json` | 退件原檔；**可能不是合法 JSON** | tick 退件 | 明確同名 add、rm，或同名 park 覆蓋時清除 |
| `K/procs/done/<pid>.json` | 完成行程的 inst 原內容 | scheduler hard-link 保存 | 同名 add／rm／再次 park 可清除 |
| `K/cpus/` | CPU 指令目錄 | init 建 | init 時裡面尚無 CPU 指令檔 |
| `K/cpus/<n>.json` | idle inst 或當前行程 inst | tick、scheduler、rm 改 | 原子 replace；swap 前先為旧行程建立 hard-link |
| `K/cpus/<n>.json.tmp` | 要換上的 idle inst | poll／park／rm 寫 | replace 到 CPU 檔 |
| `K/syscalls/` | syscall 收件匣 | init 建；CLI／外部投單；tick 讀 | 每張處理後嘗試 unlink |
| `K/syscalls/<ticket>.json` | syscall 物件 | rm CLI／module CLI／外部 | 各 writer 先暫存再 replace |
| `K/syscalls/done/` | 回音目錄 | init／tick 建 | 不自動刪資料夾 |
| `K/syscalls/done/<ticket>.json` | `{"ok":boolean,"msg":string}` | tick 寫；對應 CLI 讀 | `.tmp`→replace；rm／llm CLI 讀完會刪 |
| `K/<module NAME>/` | module 自管的慣例位置 | module 自管 | 核心沒有通用建立／清理規則 |

核心 JSON writer 是同一支 `aos_home.write_json()`，因此只有 rename 發佈，沒有 fsync 交易。

來源：[aos_kernel.py:61](../../proto4-3/aos_kernel.py)、[aos_kernel_init.py:43](../../proto4-3/aos_kernel_init.py)、[aos_kernel_schedule.py:94](../../proto4-3/aos_kernel_schedule.py)。

**3.3 `config.json` 全欄位**

| 欄位 | 正常型別 | init 旗標／預設 | 意思與驗證 |
|---|---|---|---|
| `ncpu` | 整數 | `--ncpu` 必填 | 工作 CPU 數；init 要 ≥1；不包含 kernel 自己那支 aos-run |
| `interval_ms` | 整數 | `--interval-ms 1000` | boot kernel 及新插工作 CPU 時給 aos-run 的 interval；init 要 ≥0 |
| `timeout_ms` | 整數 | `--timeout-ms 0` | boot kernel 及新插 CPU 的單次 timeout；0 不傳旗標；init 要 ≥0 |
| `quantum` | 整數 | `--quantum 5` | 有人排隊時，按 CPU 的完成 runs 差值決定輪替；init 要 ≥1 |
| `done_exit` | 整數 | `--done-exit 100` | 完成碼；0 關閉完成判定；init 不限制範圍 |
| `wait_exit` | 整數 | `--wait-exit 101` | 等待碼；init 不限制範圍，也不限制不能與其他碼相同 |
| `bad_after` | 整數 | `--bad-after 10` | 一般非零結果累計門檻；0 關閉此退件條件；init 要 ≥0 |
| `modules` | 字串陣列 | 重複 `--module PATH`；預設 `[]` | init 轉為絕對路徑；不在 init 時載入或驗存在 |

**讀取 config 比 init 驗證寬鬆：**

- 只要頂層是物件且 `ncpu` 是 Python `int` 就認為是家；`bool` 也是 int，會被接受。
- 其他所有值為 int 的 key 都併入 cfg，**包含未知 key**。
- 已知數值欄若是非 int，被忽略並用預設；`ncpu` 非 int 則整家無效。
- 不重新驗證數值範圍，手改負數／零與 bool 會進入後續邏輯。
- `modules` 不是完整 `list[str]` 就靜默變 `[]`。
- 每次 tick 重新讀 config；已存在 daemon CPU 不會因此更新 aos-run 的 flags。
- 修改 `ncpu` 沒有完整熱拔除流程：縮小時不主動刪除額外 CPU 或 daemon entries。

來源：[aos_kernel.py:86](../../proto4-3/aos_kernel.py)、[aos_kernel_init.py:27](../../proto4-3/aos_kernel_init.py)、[aos_kernel_boot.py:37](../../proto4-3/aos_kernel_boot.py)。

**3.4 inst 檔的欄位與 kernel 額外限制**

`K/inst.json`、`procs/*.json`、`cpus/*.json` 使用相同 posix inst 格式；不是另外一份「process metadata」格式。

| 欄位 | 執行器正常接受型別 | 缺省值 | kernel 特別處理 |
|---|---|---|---|
| `_metainfo` | 物件：`_type` 字串、`_version` 整數 | posix v1 | 完整 inst validator 驗；proto4 也把 null 當沒寫 |
| `argv` | 非空字串陣列，允許指示詞解析 | 必填 | add 在解析前要求 raw list 且 raw argv[0] 為字串 |
| `cwd` | 字串／指示詞／mkdir 選項物件 | inst 的 base | add 與 queue 檢查先要求 raw 字串；手放 queue 必須有此 key |
| `stdin` | 字串或 inherit 選項 | `/dev/null` | kernel 不改 |
| `stdout` | 字串或 append/mkdir/inherit 選項 | `/dev/null` | kernel 不改 |
| `stderr` | 同 stdout，另可 merge | `/dev/null` | add 未寫時印提醒；仍可加入 |
| `exit` | 字串或 append/mkdir 選項 | 不寫 | kernel 不讀它排程 |
| `envs` | 物件／指示詞／clear 選項 | `{}`，疊加繼承環境 | kernel 不改 |
| 其他頂層欄位 | 任意 | 無 | add 複製保留；aos-exec 不執行、不因普通未知欄位拒絕 |

相對 stream／exit／`$ref` 路徑由 aos-exec 以解析後 cwd 為中心處理。kernel 沒有替它們全部轉成絕對路徑。

來源：[aos_inst.py:92](../../proto4-3/aos_inst.py)、[aos_kernel_add.py:86](../../proto4-3/aos_kernel_add.py)、[aos_kernel_tick.py:104](../../proto4-3/aos_kernel_tick.py)。

**3.5 `state.json` 與一個行程的完整欄位**

頂層：

| 欄位 | 型別 | 初值 | 意思／讀取容錯 |
|---|---|---|---|
| `cpus` | 物件 | `{"0":null,...}` | CPU 編號字串→當前行程紀錄；不是物件則用 `{}` |
| `queue` | 字串陣列 | `[]` | FIFO；讀取只保留字串元素 |
| `waiting` | 物件 | `{}` | **排隊中** pid→等待計數；只保留字串 key、正 int 值，bool 也符合 int |

`cpus["n"]` 為 null 或：

| 欄位 | 正常型別 | 初值／缺省讀法 | 意思 |
|---|---|---|---|
| `pid` | 字串 | 上 CPU 的檔名 stem | 邏輯行程名稱 |
| `since` | number | 本次 tick 的 `time.time()` | 最近這次上 CPU 的時間 |
| `runs_at` | 整數 | 當時 daemon entry 的 runs | 本次 CPU 配置起點 |
| `seen_runs` | 整數 | 同 `runs_at` | kernel 已觀察過的最新 runs；舊紀錄缺少時退回 runs_at |
| `waiting` | 布林 | 缺少代表非 waiting | 最新觀察到 wait_exit 時設 true |
| `wait_runs` | 整數 | 首次從 0 累加 | 被歸為等待的新增 runs；輪替時可保存到頂層 waiting |
| `bad_runs` | 整數 | 首次從 0 累加 | 一般非零結果計數 |
| `bad_exit` | 整數 | 與 bad_runs 同時寫入 | 最近的一般非零退出碼 |
| `aos_ticks` | 整數 | 0／缺少 | 連續 tick 看到符合條件的 `kind=aos` 次數 |

沒有持久化的 proc Linux PID、每次 invocation ID、完整退出歷史、等待檔案清單、優先級、總執行次數或獨立 `state:"running"` 欄位。

狀態讀取只清理頂層容器，**不驗 `cpus` 每個 cur 的完整形狀**。壞 cur 可能讓 scheduler 或 status 丟例外。未知頂層欄位不由 `KHome.state()` 保留。

來源：[aos_kernel.py:102](../../proto4-3/aos_kernel.py)、[aos_kernel_schedule.py:26](../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_schedule.py:94](../../proto4-3/aos_kernel_schedule.py)。

**3.6 行程狀態與檔案轉換**

| 狀態 | 實際表示 | 進入／離開 |
|---|---|---|
| queued | `procs/<pid>.json`；排程時進 queue | add／手放／CPU 換下；take 後檔移去 CPU |
| running | `cpus/<n>.json`＋`state.cpus[n]` | take/swap 上 CPU；不等於此刻有 POSIX child 正在跑 |
| waiting on CPU | cur 的 `waiting:true` | 最新可觀察結果是 wait_exit；有人排隊且 ran≥1 可讓位 |
| waiting in queue | `state.waiting[pid]` | waiting 行程換下時保存；再次上 CPU 移回 cur |
| done | `procs/done/<pid>.json` | done_exit 條件成立；不再排程 |
| bad | `procs/bad/<pid>.json` | queue 格式錯、aos_ticks 達門檻或 bad_runs 達門檻 |
| removed | 指令檔刪掉，或 CPU 換 idle | rm；不留 done、bad 或 removal tombstone |
| idle CPU | cur=null；CPU 檔為 `{"argv":["true"],"cwd":"."}` | 初建、檔案遺失、done/bad/rm |

等待不是阻塞式睡眠狀態：kernel 不監看結果檔，也不把 waiting 行程移到不可執行集合。它仍會被反覆排回 CPU。

**3.7 init、boot、add**

| 動作 | 精確流程 |
|---|---|
| init | 驗 flags → DIR 已存在就拒絕 → 建目錄 → 寫 kernel inst/config/state → append init log |
| init 的 CPU | 只建 `cpus/`，不先建立 `0.json...` |
| boot | 驗 cfg 與 K/inst 是檔 → 驗 daemon PID 活 → 讀 daemon state |
| boot 冪等 | key 已有 dict entry，且 state 為 `running` 或 `paused` 就回成功；不 resume paused，不要求 ready |
| boot 其他既有態 | 仍嘗試 add，通常被 daemon 以重複 key 拒絕 |
| boot 新掛載 | 對 `K/inst.json` 投 add；傳 interval，timeout 非零時也傳；不等待第一個 kernel tick |
| add 的路徑 | INST 相對於**呼叫時 cwd**解析；給 K 不會把 INST 改成相對於 K |
| add raw 驗證 | JSON 物件；cwd 字串；argv 非空 list、argv[0] 字串 |
| add cwd | 沒寫→來源 INST 所在目錄；相對→以來源目錄轉絕對；必須已是資料夾 |
| add argv[0] | 含 `/` 且相對→以正規化 cwd 轉絕對；含 `/` 但不存在→拒絕；純 PATH 名不預查 |
| add 自動名稱 | 所有活躍＋done＋bad 的純數字名，取最大值＋1；沒有則 `"1"` |
| add 指定名稱 | 只拒絕空字串及 `/`；沒有 LLM id 那套英數限制 |
| 活躍名稱來源 | procs 現有檔＋state queue＋state cpus；舊 state 也可能占名 |
| 指定名撞 done/bad | 完整驗證通過後先清同名舊紀錄，再發佈新檔 |
| add 最後驗證 | 寫 `procs/.<name>.json.tmp` → `aos_inst.load()` → 清舊紀錄 → replace 正式 procs 檔 |
| add 的 state | 不直接修改 queue/state；下一 tick 才收進表 |

来源：[aos_kernel_init.py:24](../../proto4-3/aos_kernel_init.py)、[aos_kernel_boot.py:11](../../proto4-3/aos_kernel_boot.py)、[aos_kernel_add.py:46](../../proto4-3/aos_kernel_add.py)。

**3.8 一格 tick 的完整順序**

| 次序 | 行為與邊界 |
|---|---|
| 1 | 讀 state；為 config 指定的 CPU 補上缺少的 null key |
| 2 | 讀 daemon 的 `state.runs`；讀不到視為空表 |
| 3 | 各 CPU 指令檔若不存在，先補 idle；若原 cur 有行程，直接清成 null |
| 4 | CPU realpath key 已在 daemon 表上就放進本輪 ready；**不檢查 alive、ready、state 或 running** |
| 5 | 缺少的 key 呼叫 ctl add；每顆 subprocess timeout 20 秒；成功或失敗都記 note；**新 add 成功的 CPU 當輪仍不進 ready** |
| 6 | 依 config 順序重新載入 modules，收載入 notes |
| 7 | 按檔名字典序處理 syscalls；**每張**先辨識是否內建 rm，其他才找 module；不是先處理整批所有 rm |
| 8 | 依順序跑每個 module 的 tick |
| 9 | 檢查 procs 頂層指令檔，壞的 replace 到 bad |
| 10 | 重建 FIFO，按 CPU 編號依序排 ready CPUs |
| 11 | 原子寫 state |
| 12 | append 一行 kernel.log，正常返回 0 |

queue 基本檢查：可讀 JSON 物件、raw 有 argv、raw 有 cwd、cwd 是字串，再呼叫完整 inst validator。**沒有要求 cwd 必須為絕對路徑，也沒有在這階段執行 aos-exec 的所有 filesystem 前置檢查。**

來源：[aos_kernel_tick.py:41](../../proto4-3/aos_kernel_tick.py)、[aos_kernel_tick.py:69](../../proto4-3/aos_kernel_tick.py)、[aos_kernel_tick.py:104](../../proto4-3/aos_kernel_tick.py)。

**3.9 FIFO 與選下一個行程**

| 項目 | 算法 |
|---|---|
| present | `procs/` 頂層以 `.json` 結尾的普通檔案，去副檔名為 pid |
| 新 pid 順序 | 純數字按數值排；非數字按字串排在數字之後 |
| 相同數值名稱 | 如 `1`、`01`，沒有額外 tie-break key |
| 保留原 queue | 只保留仍 present 且不在任何 cur 的 pid |
| 加新檔 | present 裡尚未在 queue/on_cpu 的，依上述順序排尾 |
| CPU 順序 | `0..ncpu-1` |
| idle CPU | 有 queue 就取隊首；replace 到 CPU，記當前 runs 為 runs_at/seen_runs |
| 量子用完 | 只有 queue 非空且 `runs-runs_at >= quantum` 才換人 |
| waiting 讓位 | 只有 queue 非空、cur waiting、`ran>=1` 才換人 |
| 沒人排隊 | 原行程續跑，即使 waiting 或量子已超過 |
| 換人 | `link(cpu, procs/old)` → `replace(procs/new,cpu)` → 新者離隊、旧者排尾 |
| 換人失敗 | 保留原排程或嘗試撤銷 hard-link，寫 note |
| 計數保存 | waiting 計數跨 swap 保存；bad_runs/bad_exit/aos_ticks **不跨 swap 保存** |

來源：[aos_kernel.py:56](../../proto4-3/aos_kernel.py)、[aos_kernel_schedule.py:9](../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_schedule.py:111](../../proto4-3/aos_kernel_schedule.py)。

**3.10 退出碼判定的精確順序**

每個非 idle cur 先算：

```text
ran      = daemon.runs - cur.runs_at
new_runs = max(0, daemon.runs - cur.seen_runs)
```

若 daemon runs 比 seen_runs 小，先把 runs_at/seen_runs 重設成現值，並清 waiting、wait_runs、bad_runs、bad_exit、aos_ticks。

| 優先序 | 條件 | 動作 |
|---|---|---|
| 1：完成 | `done_exit != 0`、last_kind=`child`、last_exit=done_exit、`ran>=2` | park 到 done、CPU idle、cur=null；**當輪直接 return，不補下一人** |
| 2：觀察新結果 | `new_runs>0` | 更新 seen_runs，依最新 last_kind/last_exit 更新 waiting 與 bad 計數 |
| 3：執行器失敗 | last_kind=`aos` 且 `ran>=2` | 每個 kernel tick `aos_ticks += 1`；否則清為 0 |
| 4：aos 退件 | `aos_ticks>=2` | park 到 bad；當輪 return |
| 5：一般連敗 | bad_after 非零且 bad_runs≥bad_after | park 到 bad；當輪 return |
| 6：waiting | cur waiting、ran≥1、queue 非空 | swap |
| 7：量子 | ran≥quantum、queue 非空 | swap |

`_observe_exit()`：

| 最新結果 | waiting 計數 | bad 計數 |
|---|---|---|
| `child`＋wait_exit | waiting=true；wait_runs += new_runs | 清 bad_runs/bad_exit |
| `child`＋0 | 清 waiting/wait_runs | 清 bad |
| `child`＋done_exit | 清 waiting | 清 bad；完成判定在前面另做 |
| `child`＋125 | 預設下清 waiting | 清 bad；**不是 kind=aos，不走 aos_ticks** |
| `child`＋其他碼 | 清 waiting | bad_runs += new_runs；bad_exit=最新碼 |
| `aos`／`usage` | 清 waiting | 清 bad |

重要的可觀察含義：

| 事項 | 現況 |
|---|---|
| 100／101 | 只是 done_exit／wait_exit 的預設，可改 |
| done_exit=0 | 關閉完成；此時子程式的 100 會成為一般非零，仍可能因 bad_after 退件 |
| bad_after=0 | 只關閉一般非零退件；不關閉格式退件或 aos_ticks 退件 |
| 不同非零碼 | 例如 1→2→3，bad_runs 仍累加；log 最後會用最新 bad_exit 描述整串 |
| 漏看中間結果 | kernel 只看到最新碼；若 runs 一次增加 5，會把 5 次全歸到最新碼 |
| aos_ticks | 同一份未變的 `kind=aos` 快照也能連續兩個 tick 累加；不要求又完成新一次執行 |
| done | `ran>=2` 是防舊回報的門檻，不是精確 invocation 歸屬；行程退 100 仍可能再執行 |
| waiting | 不要求 ran≥2 才觀察；一般 bad 計數也沒有這道門 |
| runner 重啟辨識 | 只看 runs 是否倒退，沒有比對 daemon entry PID 或 generation |
| 退件原因 | 寫在 kernel.log；bad 指令檔沒有追加 error 欄位 |

來源：[aos_kernel_schedule.py:26](../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_schedule.py:75](../../proto4-3/aos_kernel_schedule.py)。

**3.11 換檔、執行中工作與崩潰**

| 情況 | 現況 |
|---|---|
| quantum／waiting swap | 只換 CPU 指令檔，不中斷已開始的子程式 |
| rm 正在 CPU 上的行程 | 換 idle，不等待或 kill 該次 invocation |
| done／bad park | 先寫 idle tmp，刪目的地舊同名檔，hard-link CPU 到歸檔處，再 replace idle |
| park 後有 queue | 本 CPU 該輪不補人，下輪才可能 take |
| 多 CPU | scheduler 不檢查 entry.running；剛換下的 pid 可被後面的 idle CPU 取走 |
| 同邏輯行程重疊 | 因上一 CPU 的 invocation 可尚未結束，另一 CPU 已開始相同 pid；**這是由程式流程可推導的情況，本輪未動態實跑** |
| state 消失／壞掉 | 讀成空表；不從 CPU inst 反推出原 pid |
| daemon 重啟 | 還要有人讓 kernel tick 再跑；kernel 自己不是由新 daemon 自動復原 |
| CPU daemon entry 消失 | 下一 tick 嘗試補 add；保留存在的 CPU 指令檔 |
| CPU 指令檔消失 | 補 idle，原 cur 清掉，不自動還原原行程 |
| 多個 tick 同時跑 | 沒有鎖 |
| 檔案與 state | hard-link／replace／save state 是不同步驟，沒有跨檔交易或通用 crash recovery |

來源：[aos_kernel_schedule.py:111](../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_schedule.py:158](../../proto4-3/aos_kernel_schedule.py)、[aos_kernel_syscall.py:136](../../proto4-3/aos_kernel_syscall.py)。

**3.12 內建 syscall：rm**

請求：

```json
{"op":"rm","pid":"行程名稱"}
```

回應：

```json
{"ok":true,"msg":"rm 行程名稱（原本在佇列）"}
```

| 欄位／項目 | 型別／預設／行為 |
|---|---|
| `op` | 必須辨識為 `"rm"`；其餘交 module |
| `pid` | raw syscall 要非空字串；handler **不禁止 `/`** |
| CLI NAME | CLI 另外禁止空字串及 `/` |
| 其他請求欄位 | 忽略，不複製到回應 |
| 回應 `ok` | boolean |
| 回應 `msg` | string |
| 關聯方式 | request/done 同檔名，沒有額外 correlation id |
| CLI 票名 | `<time.time_ns()>-rm-<pid>.json` |
| CLI 等待 | 固定 `max(3秒, 3×config.interval_ms/1000)`；每 0.05 秒，用 monotonic |
| `--wait` | **rm 沒有這個旗標** |
| 等到回音 | 讀取、刪 done、印 msg；ok→0，否則1 |
| 超時 | 退出1，**不撤 request**；稍後仍可刪行程 |
| 回音寫失敗 | tick 記 note，仍嘗試刪 request |
| request 刪失敗 | 記 note；下次 tick 可能重複處理 |

rm 查找順序：

| 次序 | 找到時做什麼 |
|---|---|
| 1：CPU 0..N-1 | 第一個同 pid cur 換 idle、清 cur 與 waiting，立即回成功 |
| 2：procs | unlink 指令檔、清 waiting；queue 稍後由 schedule 清 |
| 3：done 與 bad | 清兩處同名普通檔案，成功訊息列出清了哪些 |
| 全部沒有 | `ok:false`，msg 說佇列、CPU、done、bad 都沒有 |

壞 JSON、非物件、缺 op、未知 op、rm 缺 pid，都會嘗試寫負回音再刪原單。**沒有把原單搬到 done；done 是另造的回應。**

來源：[aos_kernel_syscall.py:18](../../proto4-3/aos_kernel_syscall.py)、[aos_kernel_syscall.py:72](../../proto4-3/aos_kernel_syscall.py)、[aos_kernel_syscall.py:136](../../proto4-3/aos_kernel_syscall.py)。

**3.13 module 機制**

登記方式只有 `config.modules`；init 的 `--module` 幫忙填入它，沒有動態 module 登記 syscall。

| 項目 | 契約／實作 |
|---|---|
| 檔案 | 一支 Python 檔 |
| `NAME` | 必須非空字串；作 CLI 子命令名 |
| `OPS` | 必須 tuple，每項為非空字串；允許空 tuple |
| `handle(h,cfg,st,ticket)` | 可省；回二元組 `(ok,msg)`；kernel 強制 `bool(ok),str(msg)` |
| `tick(h,cfg,st)` | 可省；回 list 才把各項轉字串、一行化加到 notes；其他回值忽略 |
| `status(h,cfg)` | 可省；非 None 的回值直接 print |
| `cli(h,cfg,argv)` | 可省；回值直接當 CLI 回碼 |
| hook 型別 | 若非 None，必須 callable；不預驗函式參數或回值型別 |
| 載入時機 | tick、ls、module CLI 各自載入 |
| import 名稱 | `aos_kernel_module_`＋絕對路徑 SHA-256 前16字元 |
| import 路徑 | 暫時把 module 所在資料夾放到 sys.path[0] |
| 隔離 | 同一個 Python process；只有例外捕捉，**不是 subprocess 或 sandbox** |
| 例外 | 載入及 hooks 捕捉 `BaseException`，包括 SystemExit |
| 重複 NAME／OPS | 不拒絕；依 config 順序選第一個符合者 |
| 內建 rm | 優先於任何 module 的同名 op |
| CLI 找 K | 在 module 後面的**前兩個參數**中找含 config.json 的資料夾，找到後抽掉；否則用 cwd |
| 載入失敗顯示 | tick 記 log note，ls 印 note；module CLI 不會統一印所有 load notes |

module 可以改動傳入的 state；核心不對 module 的副作用做回滾。

來源：[aos_kernel_module.py:16](../../proto4-3/aos_kernel_module.py)、[aos_kernel.py:171](../../proto4-3/aos_kernel.py)、[aos_kernel_status.py:92](../../proto4-3/aos_kernel_status.py)。

**3.14 `ls` 的輸出來源**

| 顯示 | 計算／來源 |
|---|---|
| daemon 家 | **只讀環境變數 `AOS_DAEMON_HOME`**；沒有使用 `~/.aos-daemon` fallback |
| 找不到家 | env 沒設／空，或該路徑不是資料夾 |
| daemon 沒在跑 | 找得到家，但 state 沒有整數 pid |
| daemon alive/dead | 用 daemon state 的 pid 檢查 `/proc`；不是讀 daemon.pid |
| CPU | 0..ncpu-1 |
| PROC | cur.pid；null 顯示 idle |
| ON | `time.time()-since`，一位小數秒 |
| RUNS | daemon.runs−cur.runs_at；無資料顯示 `-`；不保證是行程歷來總次數 |
| LAST_EXIT | 有 cur、差值非零才顯示；kind=aos 顯示 `125(aos)`；剛換上 runs=0 顯示 `-` |
| CPU_STATE | daemon entry.state；沒 entry 顯示「沒插上」；cur waiting 時覆蓋成 waiting |
| WAIT | cur.wait_runs，文字「等了 N 回合」 |
| 佇列 | state.queue；waiting map 有紀錄則附等待次數 |
| bad | bad 目錄普通檔案數；原因從 kernel.log 倒找最近含「退件」的行，不是逐檔 error |
| done | done 下 `.json` stem，按 pid 規則排序 |
| module | 各 module status hook 輸出 |

`ls` 不推 tick、不修 queue、不補 CPU；daemon dead 或 module status 出錯，正常仍可退出 0。

來源：[aos_kernel_status.py:9](../../proto4-3/aos_kernel_status.py)。

**3.15 LLM module：kernel 實際接到的介面**

`proto4-5/llm_cpu_module.py`：

```python
NAME = "llm"
OPS = ("llm",)
```

它使用全部四個 hook。家固定 `K/llm/`，由 module tick 第一次建立；**不建 `K/llm/inst.json`**，因為排程由 kernel tick 直接呼叫。

核心只傳遞 ticket 和呼叫 hook；以下 LLM 格式由 proto4-5 實作，不是 kernel 核心驗證。

LLM syscall：

```json
{
  "op": "llm",
  "id": "hello",
  "request": {
    "messages": [{"role":"user","content":"hi"}]
  }
}
```

| 欄位 | 型別／預設 | 行為 |
|---|---|---|
| `op` | `"llm"` | module dispatch |
| `id` | 字串或 null，可省 | null／未提供由 submit 產生 time_ns 名称；空字串也走自動產名 |
| `request` | 物件，實際必填 | 內嵌完整 LLM 請求，不是檔案路徑 |
| syscall 回應 | `{"ok":bool,"msg":str}` | 只代表排單結果，**不是模型結果** |

ID 通過 submit 時須符合 `[A-Za-z0-9._-]+`，不能為 `.`、`..` 或 `.tmp` 結尾。

module handle 先讀 endpoints、驗請求，再做同名檢查與 submit。**handle 不先 ensure LLM 家；kernel 順序又是 syscall 在 module.tick 前，因此首個 tick 尚未建家時，預先放入的 llm syscall 可先失敗，之後才建家。**

來源：[llm_cpu_module.py:13](../../proto4-5/llm_cpu_module.py)、[llm_cpu_module.py:37](../../proto4-5/llm_cpu_module.py)、[llm_cpu_request.py:15](../../proto4-5/llm_cpu_request.py)。

**LLM CLI 與 `--wait`**

```text
aos-kernel llm [K] REQ.json|- [--name NAME] [--wait SECS] [--json]
aos-kernel llm ls K
aos-kernel llm rm K NAME
```

| 項目 | 行為 |
|---|---|
| `REQ.json|-` | CLI 讀 JSON 檔或 stdin，嵌入 ticket |
| `--name` | 預設 `str(time.time_ns())` |
| `--wait SECS` | float 秒數；預設無；只拒絕 `<0`，沒有有限數檢查 |
| `--json` | 等結果後印完整結果 JSON；無 wait 時不改成印結果 |
| 第一期等待 | 新單無論有無 `--wait`，都等 syscall 回音；上限 `max(3秒,3×interval_ms/1000)` |
| 第二期等待 | `--wait` 才進入，從收到成功回音後另算 SECS，輪詢 result 檔 |
| 輪詢頻率 | 每 0.05 秒，monotonic |
| 是否推 tick | 不會 |
| 是否先檢 daemon/kernel PID | 不會；判斷依據是回音、檔案是否出現 |
| syscall 回音讀完 | unlink done 回音 |
| 第一期逾時 | 若原 syscall 還可 unlink，印「沒送出去，已撤單」；若已不存在，印「已送出，還沒做完」；退出 1 |
| 第二期逾時 | 不撤已送出的請求，印未完成與 result 路徑，退出 1 |
| 無 wait 成功 | 印結果路徑，退出 0 |
| 有 wait 成功結果 | 預設印 text＋路徑；`--json` 印 JSON＋路徑；退出 0 |
| 有 wait 失敗結果 | 印 error 或完整 JSON＋路徑；退出 1 |
| CLI 用法／讀輸入錯 | 2；`--help` 也被 SystemExit catch 轉成 2 |
| `llm ls` | 直接讀 LLM 家，可在 daemon 不活時使用 |
| `llm rm` | 直接刪 LLM 家資料；running 先 TERM worker group、等1秒，再 KILL、等1秒；不經 syscall |

第一期撤單不是交易式取消：kernel 可能已讀 request 但尚未刪原檔；CLI 判斷只是檔案是否還存在。

來源：[llm_cpu_module.py:98](../../proto4-5/llm_cpu_module.py)、[llm_cpu_module.py:174](../../proto4-5/llm_cpu_module.py)、[llm_cpu_module.py:233](../../proto4-5/llm_cpu_module.py)、[llm_cpu_manage.py:85](../../proto4-5/llm_cpu_manage.py)。

**3.16 `K/llm/` 檔案與完整欄位**

| 路徑 | 格式／誰寫誰讀 | 搬移／刪除 |
|---|---|---|
| `endpoints.json` | module 初建範例；使用者改；handle/tick/worker/status 讀 | `.tmp`→replace |
| `requests/<id>.json` | request＋`_aos`；handle submit 寫；tick 讀 | dispatch 時 replace 到 running；壞單移 done |
| `requests/running/<id>.json` | 帶 worker metadata 的 request；tick 寫；worker/後續 tick 讀 | 結果存在、worker 死或逾時後移 done |
| `requests/done/<id>.json` | 原 request 與既有 `_aos` | 保留；llm rm 刪 |
| `results/<id>.json` | worker 或 scheduler 寫結果；CLI／agent 讀 | `.tmp`→replace；llm rm 刪；讀完不刪 |
| `state.json` | 最近 tick 的儀表 | 每 tick 原子覆寫 |
| `usage.jsonl` | worker append，每行 JSON | 不自動清理；llm rm 不刪歷史 |
| `llm-cpu.log` | tick 文字 append | 不自動清理 |
| `log/<id>.log` | worker stderr append | llm rm 不刪 |
| 各 `<path>.tmp` | 原子發佈暫存 | 正常 replace；沒有通用回收 |
| `inst.json` | module 模式**不建立** | 獨立 llm-cpu 模式才有 |

LLM `atomic_json()` 會 fsync **檔案**後 replace，但沒有 fsync 父目錄。其 syscall 發佈包了兩層暫存，會先經 `<ticket>.json.tmp.tmp`，再到 `.tmp`，最後正式 `.json`。

來源：[llm_cpu_home.py:15](../../proto4-5/llm_cpu_home.py)、[llm_cpu_home.py:43](../../proto4-5/llm_cpu_home.py)、[llm_cpu_module.py:218](../../proto4-5/llm_cpu_module.py)。

`endpoints.json`：

| 欄位 | 型別 | 預設／要求 |
|---|---|---|
| `default` | 字串 | 初建 `"local"` |
| `endpoints` | 物件陣列 | 初建只一個 local；name 不可重複 |
| `endpoints[].name` | 字串 | 初建 `"local"`；home loader 要字串，實際呼叫再要求非空 |
| `.kind` | 字串 | 初建 `"openai"`；排程只接受 openai |
| `.base_url` | 非空字串 | 初建 `http://localhost:1234/v1` |
| `.model` | 非空字串 | 初建 `"loaded-model-id"` |
| `.max_concurrent` | 正整數，非 bool | 初建 `1`；排程必需 |
| `.timeout_ms` | 正整數，非 bool | 初建 `300000`；排程必需 |
| `.enabled` | 預期布林 | 省略當 true；必須是 `True` 才派工 |
| `.api_key_env` | 非空字串，可省 | 指環境變數名稱，未提供則不加 Bearer key |
| `.strict_model` | 布林，可省 | 呼叫層預設 true |

LLM request：

| 欄位 | 型別／預設 | 驗證／用途 |
|---|---|---|
| `messages` | 非空陣列，必填 | 排程只驗陣列非空；元素沒有完整 schema 驗證 |
| `endpoint` | 字串，可省 | 省略用 endpoints.default；須存在 |
| `priority` | 整數，非 bool；預設0 | 越大越先，允許負數 |
| `timeout_ms` | 正整數，非 bool，可省 | 省略使用 endpoint timeout |
| `params` | 物件，可省 | 併入 HTTP body；model/stream 最後由呼叫層覆蓋固定 |
| `tools` | 陣列，可省 | 排程驗證未檢此欄；worker 呼叫層驗陣列，內容原樣傳 |
| `tool_choice` | 任意 JSON，可省 | 呼叫層原樣傳，不驗 schema |
| `id` | 未嚴格驗型別，可省 | worker 會覆蓋成檔名 id |
| `model` | 不允許出現 | 出現即拒絕，即使值為 null |
| `_aos` | 物件 metadata，可省 | submit/dispatch 增補；其他自帶 metadata 可保留 |
| 其他 key | 任意 | 留在儲存 request；HTTP 不會整包原樣傳送 |

`_aos` 全部由現有排程器產生的欄位：

| 欄位 | 型別 | 初值／寫入時機 |
|---|---|---|
| `request_sha256` | 64字元十六進位字串 | submit 算正規化請求指紋 |
| `submitted` | UTC ISO-8601 字串，毫秒精度 | submit 時 |
| `endpoint` | 字串 | dispatch 選定 endpoint 時 |
| `pid` | 整數或 null | dispatch 先 null；worker Popen 後改 Linux PID |
| `started` | number | dispatch 的 `time.time()` |

指紋是 `sort_keys=True`、緊湊 JSON、UTF-8 的 SHA-256；會排除 `_aos` 裡上述五個排程器欄位。**不會補齊 endpoint/default、priority 等語意預設再比較**，所以省略預設與明寫預設不必然是相同指紋。

同名查找順序：requests → running → results → done。內容同指紋視為既有同單；不同則拒絕。CLI 命中同單可直接成功或等既有 result，無須 kernel 活著。

來源：[llm_cpu_home.py:115](../../proto4-5/llm_cpu_home.py)、[llm_cpu_request.py:21](../../proto4-5/llm_cpu_request.py)、[llm_cpu_tick.py:110](../../proto4-5/llm_cpu_tick.py)、[aos_llm.py:89](../../proto4-5/aos_llm.py)。

result 全欄位：

| 欄位 | 型別／值 | 寫入與含義 |
|---|---|---|
| `ok` | boolean | 成功／失敗 |
| `id` | 字串 | request 檔名 id |
| `endpoint` | 字串或 null | 選定 endpoint；無法辨識時 null |
| `model` | 供應商原值，通常字串或 null | 實際回應 model；無有效回應通常 null |
| `model_requested` | 字串或 null | endpoint 設定的 model |
| `text` | 供應商 content 原值，通常字串或 null | 不做嚴格字串驗證 |
| `finish_reason` | 供應商原值或 null | 第一個 choice 的 finish_reason |
| `usage` | 物件 | 下列五欄 |
| `usage.prompt` | 通常整數或 null | prompt_tokens 原值 |
| `usage.completion` | 通常整數或 null | completion_tokens 原值 |
| `usage.total` | 通常整數或 null | total_tokens 原值 |
| `usage.cached` | 通常整數或 null | prompt_tokens_details.cached_tokens 原值 |
| `usage.reasoning` | 通常整數或 null | completion_tokens_details.reasoning_tokens 原值 |
| `ms` | 整數 | 呼叫耗時毫秒；scheduler 自造錯誤為0 |
| `raw` | 任意 JSON 或 null | 原供應商資料；不限定額外欄位 |
| `notes` | 陣列 | worker 呼叫結果有，通常 `[]`；**scheduler 的 `_error_result()` 不寫此欄** |
| `notes[].kind` | 字串 | 目前可有 `model_preflight_skipped` |
| `notes[].msg` | 字串 | 預檢失敗但仍送 chat 的說明 |
| `notes[].error` | 錯誤物件 | 預檢錯誤，形狀同 error |
| `error` | null 或物件 | 成功 null；失敗如下 |
| `error.kind` | 字串 | 錯誤種類 |
| `error.msg` | 字串 | 錯誤說明 |
| `error.status` | 整數或 null | HTTP status 或無 |
| `error.retryable` | boolean | 資訊標記，沒有自動重試 |
| `request_sha256` | 字串或 null | worker／scheduler 加到結果，供同單辨識 |

`raw` 的供應商資料不是 kernel 定義的固定 schema；agent 用到其中的 `choices[0].message`，包含可能的 `tool_calls`。

來源：[aos_llm.py:24](../../proto4-5/aos_llm.py)、[aos_llm.py:186](../../proto4-5/aos_llm.py)、[llm_cpu_tick.py:15](../../proto4-5/llm_cpu_tick.py)、[llm_cpu_worker.py:37](../../proto4-5/llm_cpu_worker.py)。

其他 JSON：

| 檔／欄位 | 型別、初值、寫入者 |
|---|---|
| state `ticks` | 整數，初值0；每次成功走到存檔的 llm tick＋1 |
| state `running` | 整數，初值0；running 數量 |
| state `endpoints` | 物件，初值 `{}`；endpoint name→running 整數 |
| usage `at` | UTC ISO 字串；worker 寫 |
| usage `id` | 字串 |
| usage `endpoint` | 字串或 null |
| usage `model` | 供應商原值或 null |
| usage `prompt` | token 原值或 null |
| usage `completion` | token 原值或 null |
| usage `total` | token 原值或 null |
| usage `cached` | token 原值或 null |
| usage `reasoning` | token 原值或 null |
| usage `ms` | 整數 |
| usage `ok` | boolean |

usage 由 worker 寫結果後 append；scheduler 自己退的壞單、spawn 失敗等沒有經 worker 的 usage 寫入路徑。

**3.17 LLM 每格排程與生命週期**

| 次序 | 動作 |
|---|---|
| 1 | 讀 endpoints；失敗只記 emergency log，這格返回 |
| 2 | 收 running：result 存在即搬 request 到 done |
| 3 | running metadata 壞／worker PID 不活且無 result | 寫 `worker_died` result，再搬 done |
| 4 | worker 超過 request/endpoint timeout＋5000ms | TERM worker PID，寫 timeout result，搬 done |
| 5 | 驗 queued requests | 壞單寫 bad_request result，搬 done |
| 6 | 排序 | priority 降冪 → request mtime_ns 升冪 → 檔名字典序 |
| 7 | 派工 | endpoint 未滿 max_concurrent 才派；request 加 metadata，移 running，開背景 worker |
| 8 | worker 啟動 | Python subprocess，`start_new_session=True`，stdin/stdout `/dev/null`，stderr 寫 log/id.log |
| 9 | Popen 失敗 | 寫 spawn result，request 搬 done |
| 10 | 寫 state、append llm-cpu.log | state 只是最近儀表；資料夾位置與 result 才是各單現況 |

worker 不透過 daemon add，也不占用 `K/cpus/n.json` 的一個普通行程槽。kernel tick 結束後它仍可繼續。沒有通用「daemon stop 就收掉所有 LLM worker」的路徑。

來源：[llm_cpu_tick.py:72](../../proto4-5/llm_cpu_tick.py)、[llm_cpu_tick.py:192](../../proto4-5/llm_cpu_tick.py)、[llm_cpu_tick.py:231](../../proto4-5/llm_cpu_tick.py)。

**3.18 kernel 必須支撑的既有使用事實**

| 使用者 | 現有依賴 |
|---|---|
| proto4-5 LLM module | config module 路徑、NAME/OPS、四 hook、syscall request/done、每 tick 呼叫 module |
| LLM 背景 worker | kernel module 的同步一格能派出跨 tick 存活的 subprocess |
| LLM 呼叫者 | syscall 成功與模型完成分兩階段；以 result 檔出現判斷結果 |
| proto4-7 agent idle | 沒信時保存自身狀態，退出101 |
| agent ask | 組 messages/tools，透過 `aos_py.llm_submit()` 呼叫 `aos-kernel llm ... --name ...`；不加 `--wait`；成功保存 result 路徑，退出0 |
| agent wait | result 未出現時退出101；由 agent 自己數到600次檢查，不是 kernel 的等待期限 |
| agent 結果處理 | 讀 `ok/error` 與 `raw.choices[0].message`，不是讀 syscall msg |
| agent 收工 | `agent.json.stop is true` 時退出100 |
| agent 錯誤 | 一般模型錯誤自行記帳，通常退出0；設定／資料等真正錯誤退出1 |
| agent kernel 設定 | README 要求使用 `bad_after=0`；這不關掉 kernel 的 aos 自身失敗退件 |
| agent 請求身份 | `<name>-e<epoch>-q<question>-s<step>`；reset 增 epoch，避免撞舊單 |
| result 保存 | agent 不替 LLM 排程清帳，結果保留在 K |

這些是現有程式的依賴；**沒有要求 kernel 知道 agent 的四格、信箱、工具或 messages 格式**。

來源：[proto4-5/README.md:101](../../proto4-5/README.md)、[proto4-7/README.md:57](../../proto4-7/README.md)、[state_machine.py:94](../../proto4-7/state_machine.py)、[state_machine.py:172](../../proto4-7/state_machine.py)、[aos_py.py:150](../../proto4-6/aos_py.py)。

**3.19 錯誤代號**

kernel 核心自己的 CLI／syscall **沒有統一具名 error code**，多為中文 msg＋退出1/2。inst 驗證則保留下列 `InstError.code`：

| 代號 | 現在用途 |
|---|---|
| `ReadFailed` | inst 讀不到 |
| `JsonSyntax` | inst JSON 語法錯 |
| `NotAnObject` | 頂層解完非物件 |
| `MetainfoInvalid` | metainfo 非物件或缺必要欄位；null 例外被當預設 |
| `UnsupportedInstType` | `_type` 不是 `"posix"` |
| `UnsupportedInstVersion` | `_version` 不是整數1，bool 也拒絕 |
| `EmptyArgv` | argv 缺少、空，或第一項空字串 |
| `FieldTypeMismatch` | 欄位解完型別不符 |
| `EnvKeyInvalid` | 環境 key 不合法 |
| `UnknownDirective` | 不認得的指示詞 |
| `DirectiveValueTypeMismatch` | 指示詞／選項值型別不符 |
| `FormatVariableInvalid` | fmt 變數名不合法 |
| `UnknownOption` | 不支援或重複的 option |
| `OptionConflict` | 選項互斥或帶值條件不符 |
| `EnvironmentVariableMissing` | env 變數不存在 |
| `UnknownFormatVariable` | 模板使用未定義變數 |
| `ReferenceReadFailed` | ref 檔讀不到 |
| `ReferenceJsonInvalid` | ref 檔不是合法 JSON |
| `ReferencePointerInvalid` | pointer 語法／位置不合法 |
| `ReferenceCycle` | 同一解析鏈重遇相同文件及位置 |

來源：[aos_inst.py:76](../../proto4-3/aos_inst.py)、[aos_inst_resolve.py:27](../../proto4-3/aos_inst_resolve.py)。

LLM result 的 `error.kind`：

| 種類 | 來源 |
|---|---|
| `bad_request` | 請求／endpoint 不合格 |
| `no_api_key` | 指定環境變數不存在 |
| `http` | HTTP 錯誤 |
| `connect` | 連線錯誤 |
| `timeout` | HTTP timeout，或排程器判 worker 超時 |
| `bad_json` | 回應不是合法 JSON／不是物件 |
| `bad_response` | 回應缺必要結構 |
| `model_not_found` | strict 預檢不含要求模型 |
| `model_mismatch` | 實際回覆模型不符 |
| `worker_died` | running 壞記錄，或 worker 消失無結果 |
| `spawn` | worker 起不來 |
| `internal` | worker 外圍捕捉到其他例外 |

HTTP 429／5xx、一般連線與 HTTP timeout 可標 retryable=true；這個欄位本身不觸發重試。

**3.20 測試旁證範圍**

| 測試 | 已有斷言 |
|---|---|
| [test_kernel_init.py:19](../../proto4-3/test/test_kernel_init.py) | init 檔案／預設、拒絕重灌、add 正規化／配名、queue 退件、syscall 回音 |
| [test_kernel_exit.py:18](../../proto4-3/test/test_kernel_exit.py) | waiting 保留／讓位、bad_after、runs 倒退清計數、特殊碼清連敗 |
| [test_kernel_daemon.py:14](../../proto4-3/test/test_kernel_daemon.py) | boot flags、done、125 退件、FIFO 輪替、CPU 補回、換檔不留空窗 |
| [test_kernel_fix_r6.py:50](../../proto4-3/test/test_kernel_fix_r6.py) | 清 done/bad、同名重排、daemon 狀態文案、欄寬 |
| [test_module.py:51](../../proto4-3/test/test_module.py) | module 路徑、tick/status/cli/syscall、缺 module 不打死 tick |
| [proto4-5/test/test_module.py:198](../../proto4-5/test/test_module.py) | LLM 等回單撤單、結果超時、同名同指紋、既有 result 等待 |

測試沒有把「最新快照推算」變成完整事件歷史，也沒有提供跨 swap 連敗保存、單行程不重疊執行或 crash transaction 的保證。

---

**4. 文件與程式碼的落差，以及 proto5 相容性**

**4.1 proto4-3 文件直接不符或描述過強**

| 文件說法與位置 | 程式現在做什麼 | 程式位置 |
|---|---|---|
| README 說 add 多寫欄位「會被擋」。[README:67](../../proto4-3/README.md) | 普通未知頂層 key 已忽略；docs/kernel 已改成忽略 | [aos_inst.py:92](../../proto4-3/aos_inst.py)、[docs/kernel.md:93](../../proto4-3/docs/kernel.md) |
| README 說 aos-run 整合 daemon 是之後的事。[README:112](../../proto4-3/README.md) | daemon 已直接啟動 aos-run 並讀 status pipe | [aos_daemon.py:66](../../proto4-3/aos_daemon.py) |
| README 說 exit 父目錄不會 mkdir。[README:117](../../proto4-3/README.md) | exit 支援 `$opt:"mkdir"`；只有未開選項才不建 | [aos_exec.py:121](../../proto4-3/aos_exec.py) |
| README 範例 add `my-proc.json` 沒指定名，下一行 rm `my-proc`。[README:54](../../proto4-3/README.md) | 自動名是數字，首次通常1，不是來源 stem | [aos_kernel_add.py:106](../../proto4-3/aos_kernel_add.py) |
| README 測試數寫243。[README:31](../../proto4-3/README.md) | 本輪靜態數 `test_*.py` 有322個 `test_*` 函式定義；不是本輪通過數 | `proto4-3/test/` AST 靜態統計 |
| daemon 文件說主迴圈不等人。[daemon.md:62](../../proto4-3/docs/daemon.md) | reap 對每筆兩 thread 各 join 最多1秒；檔案操作也是同步 | [aos_daemon.py:195](../../proto4-3/aos_daemon.py)、[aos_daemon_entry.py:172](../../proto4-3/aos_daemon_entry.py) |
| state「每0.5秒」，ls 最多看到0.5秒前。[daemon.md:133](../../proto4-3/docs/daemon.md)、[daemon.md:170](../../proto4-3/docs/daemon.md) | 0.5是每輪後的存檔門檻；輪間另睡0.2，工作時間也會延遲；沒有0.5秒最大陳舊保證 | [aos_daemon_lifecycle.py:29](../../proto4-3/aos_daemon_lifecycle.py) |
| request 處理後「搬到 done」。[daemon.md:103](../../proto4-3/docs/daemon.md) | 先 remove 原單，再另寫回應；存在失單窗口 | [aos_daemon_req.py:75](../../proto4-3/aos_daemon_req.py) |
| ctl 等 rm/restart/pause 到位「才印結果」。[daemon.md:174](../../proto4-3/docs/daemon.md) | 先印原始 ok/result，再等到位，之後另印完成文字 | [aos_daemon_ctl.py:133](../../proto4-3/aos_daemon_ctl.py) |
| daemon 收工／五秒強殺的文字容易涵蓋整個工作樹。[daemon.md:57](../../proto4-3/docs/daemon.md)、[daemon.md:121](../../proto4-3/docs/daemon.md) | KILL 的是 aos-run group；inst 在另一 session/group，不能據此保證整棵子孫清掉 | [aos_daemon_entry.py:166](../../proto4-3/aos_daemon_entry.py)、[aos_exec.py:190](../../proto4-3/aos_exec.py) |
| run 文件把 time-limit 稱硬時限。[run.md:81](../../proto4-3/docs/run.md) | 透過縮短 subprocess timeout，未涵蓋所有同步前置處理時間，且有TERM grace | [aos_run.py:126](../../proto4-3/aos_run.py)、[aos_exec.py:201](../../proto4-3/aos_exec.py) |
| kernel tick「一律0」。[kernel.md:57](../../proto4-3/docs/kernel.md) | 有參數2、非家1；未捕捉例外也可異常退出 | [aos_kernel_tick.py:140](../../proto4-3/aos_kernel_tick.py) |
| queue 的 cwd「一定要寫死」，理由是搬到 CPU 不可改中心。[kernel.md:111](../../proto4-3/docs/kernel.md) | 只驗 key 存在且 raw 是字串，接受相對 cwd；搬移後 base 可由 procs 變 cpus | [aos_kernel_tick.py:115](../../proto4-3/aos_kernel_tick.py) |
| 完成後換 idle，再看 quantum。[kernel.md:115](../../proto4-3/docs/kernel.md) | `_finish()` 後立即 return，當輪不再排該 CPU | [aos_kernel_schedule.py:42](../../proto4-3/aos_kernel_schedule.py) |
| 「v1 的行程不會自己結束」。[kernel.md:127](../../proto4-3/docs/kernel.md) | 現在已有 done_exit 與 bad 退件 | [aos_kernel_schedule.py:42](../../proto4-3/aos_kernel_schedule.py) |
| module CLI 只有第一個參數會當 K。[kernel.md:84](../../proto4-3/docs/kernel.md) | 搜尋前兩個參數，所以可 `llm ls K`、`llm rm K NAME` | [aos_kernel.py:175](../../proto4-3/aos_kernel.py) |
| config 的 ncpu 至少1等條件列為欄位限制。[files.md:43](../../proto4-3/docs/files.md) | 這些限制只在 init CLI；直接讀 config 不重驗範圍，bool也接受 | [aos_kernel.py:93](../../proto4-3/aos_kernel.py) |

「七個動作」是七個 table 方法；加上 `stop` 後，**外部請求 op 有八個**。若寫請求協議，不能只列七種。

**4.2 文件有提到，但不足以直接當精確協議的地方**

| 文件概述 | 必須一併記錄的程式事實 | 位置 |
|---|---|---|
| 連續非零 N 次退件 | 不同非零碼仍累加；差額 runs 全算成最新碼；swap 會丟失一般連敗計數 | [schedule.py:75](../../proto4-3/aos_kernel_schedule.py)、[schedule.py:133](../../proto4-3/aos_kernel_schedule.py) |
| 連續125退件 | 指 kind=aos 的連續 tick 觀察；預設下 child 125 不退件；同快照可計兩次 | [schedule.py:51](../../proto4-3/aos_kernel_schedule.py) |
| CPU 在 daemon 表上即可使用 | 未檢 entry.state、alive、ready；stopping/paused/陳舊快照也可被排程 | [tick.py:81](../../proto4-3/aos_kernel_tick.py) |
| CPU 缺少會補 add | add 成功當輪仍不排，下一 tick 才重新觀察 | [tick.py:85](../../proto4-3/aos_kernel_tick.py) |
| boot 重複無害 | 只對快照 state=running/paused 直接成功；pause_pending/stopping/restarting 不在此分支 | [boot.py:31](../../proto4-3/aos_kernel_boot.py) |
| 原子換 CPU 檔 | 只保證單檔替換，不保證 invocation 歸屬、行程不重疊或跨檔 crash recovery | [schedule.py:111](../../proto4-3/aos_kernel_schedule.py) |
| rm 等 kernel 回覆 | CLI 超時不撤單，之後仍可能刪除 | [syscall.py:53](../../proto4-3/aos_kernel_syscall.py) |
| module 錯誤隔離 | 同 process 捕捉例外，沒有副作用回滾或資源隔離 | [module.py:16](../../proto4-3/aos_kernel_module.py) |

proto4-5 相鄰文件還有兩處與 kernel 接口有關的落差：

| 文件 | 實作 |
|---|---|
| [README:118](../../proto4-5/README.md) 說 kernel 沒活著就撤單、不排隊 | CLI 沒有直接活性檢查；先投單並等回音，超時才依原檔是否存在嘗試撤單。[module.py:148](../../proto4-5/llm_cpu_module.py) |
| [README:116](../../proto4-5/README.md)／CLI 文字說「下一回合處理」 | syscall handle 與 module.tick 在同一 kernel tick 順序執行，新接受請求可在**同格**被 dispatch。[kernel_tick.py:50](../../proto4-3/aos_kernel_tick.py) |
| [README:181](../../proto4-5/README.md) 說沒有取消 | 已有 `llm rm` 直接終止 running worker 並刪四處資料；但沒有通用取消 syscall／交易式取消。[manage.py:107](../../proto4-5/llm_cpu_manage.py) |

**4.3 proto4-3 與 proto5 `exec.md`／`inst-posix.md` 的實質差異**

先保留文件自身的成熟度：proto5 的 [README:13](../README.md) 將 inst-posix 標為定稿；[exec.md:7](../spec/aos-exec/README.md) 明寫命令列尚未逐條拍板。因此下表區分「定稿格式差異」與「目前 exec 文件差異」。

| 項目 | proto5 文件 | proto4-3 現碼 | 影響／來源 |
|---|---|---|---|
| 省略 aos-exec 目標 | `xxx` 省略＝`.`。[exec.md:22](../spec/aos-exec/usage.md) | `aos-exec` 的 xxx 必填；缺少退出2 | [aos_exec.py:270](../../proto4-3/aos_exec.py)。這是 exec CLI 文件差異；不代表 aos-run 也應省略目標 |
| `_metainfo:null` | 有寫時必須是物件。[inst-posix.md:36](../spec/inst-posix/metainfo.md) | `obj.get()` 取得 None，再直接套 posix v1 預設 | [aos_inst.py:100](../../proto4-3/aos_inst.py)、[aos_inst.py:142](../../proto4-3/aos_inst.py)。本輪記憶體檢查確認接受 |
| `$ref` 字串內 `#位置` | inst 文件明示 `#` 前空＝本文件，完整語法交 directives。[inst-posix.md:179](../spec/inst-posix/directives.md) | 整個 `$ref` 字串都當檔名，`#` 不切開 | [aos_inst_resolve.py:231](../../proto4-3/aos_inst_resolve.py)。`x.json#/a` 會找檔名含 `#` 的路徑 |
| 外部 `$ref` 的相對位置 | proto5 以被引檔根作目前位置，允許 `./a`。[directives.md:128](../spec/directives/ref.md) | 只有 `$ref:""` 才准相對 `$at`；指外部檔的 `./a` 拒絕 | [aos_inst_resolve.py:248](../../proto4-3/aos_inst_resolve.py)、[aos_inst_resolve.py:281](../../proto4-3/aos_inst_resolve.py) |
| `$at:null` | 有寫必須字串，否則 DirectiveValueTypeMismatch。[directives.md:124](../spec/directives/ref.md) | `.get("$at")` 得 None，當省略，取整份 | [aos_inst_resolve.py:103](../../proto4-3/aos_inst_resolve.py)、[aos_inst_resolve.py:274](../../proto4-3/aos_inst_resolve.py) |
| `$fmt` 內位置 | 原始 JSON 實體路徑，含 `$fmt` 這層。[inst-posix.md:181](../spec/inst-posix/directives.md) | 變數用 `ctx.down(name)`，模板用 `ctx.down("$val")`，少 `$fmt` 層 | [aos_inst_resolve.py:202](../../proto4-3/aos_inst_resolve.py)。本輪確認 fmt 兄弟變數相對 ref 可因此 PointerInvalid |
| cwd mkdir 時序 | 先建 cwd，再以它為中心解其他欄位。[inst-posix.md:231](../spec/inst-posix/exec.md) | `aos_inst.load()` 先解全部欄位，回到 `_run_inst()` 才 makedirs | [aos_inst.py:102](../../proto4-3/aos_inst.py)、[aos_exec.py:116](../../proto4-3/aos_exec.py)。讀／驗失敗時 cwd 尚未建立 |
| `kind=aos` 一律等於沒跑 | proto5 exec 說 aos 是根本沒跑，125不寫exit。[exec.md:59](../spec/aos-exec/exit.md)、[exec.md:63](../spec/aos-exec/exit.md) | child 已完成後，exit 寫入或 fsync 失敗仍轉 `(1,"aos")`→125 | [aos_exec.py:226](../../proto4-3/aos_exec.py)。125不能絕對推論沒有子程式副作用；exit也可能已部分寫入 |
| timeout 收整個 group | 規範要求先TERM、2秒後必要時KILL整群。[inst-posix.md:246](../spec/inst-posix/exec.md) | KILL 時用 `os.getpgid(p.pid)`；若直接 child 已被 wait 回收，可能取不到原 pgid | [aos_exec.py:203](../../proto4-3/aos_exec.py)、[aos_exec.py:218](../../proto4-3/aos_exec.py)。不能把最後補 KILL 的程式碼當作對仍活孫程序的完整保證；本輪為靜態判讀 |

其中 `$ref #位置` 與 `$fmt` 實體位置，正是 proto4-3 README 所說未跟上的 K／L，**不是 README 錯報已凍結的範圍**。

**4.4 合法 proto5 inst 不一定能直接交給 proto4-3 kernel**

這是 kernel 的**輸入子集差異**；不能全部算作 aos-exec 本身違反 inst 規範。

| proto5 合法格式／執行語意 | proto4-3 kernel 限制 | 位置 |
|---|---|---|
| 頂層整份可為 `$ref` 等指示詞 | add raw 檢查要直接有可用 argv；queue raw 也要 argv/cwd，尚未解就拒絕 | [aos_kernel_add.py:83](../../proto4-3/aos_kernel_add.py)、[aos_kernel_tick.py:113](../../proto4-3/aos_kernel_tick.py) |
| cwd 可為指示詞 | add／queue 要 raw 字串 | [aos_kernel_add.py:87](../../proto4-3/aos_kernel_add.py)、[aos_kernel_tick.py:119](../../proto4-3/aos_kernel_tick.py) |
| cwd 可為 `$opt:mkdir`，允許目錄尚不存在 | add 先因非字串拒絕；字串不存在也拒絕；手放 queue 同樣不接受 cwd 選項物件 | [aos_kernel_add.py:88](../../proto4-3/aos_kernel_add.py) |
| argv 整包可由 `$ref` 得到 | add 要 raw list | [aos_kernel_add.py:96](../../proto4-3/aos_kernel_add.py) |
| argv[0] 可由 `$env/$fmt/$ref` 得到 | add 要 raw argv[0] 是字串 | 同上 |
| 缺 cwd 使用 inst base | add 會補絕對 cwd；手放 procs 缺 cwd 直接退件 | [aos_kernel_add.py:86](../../proto4-3/aos_kernel_add.py)、[aos_kernel_tick.py:117](../../proto4-3/aos_kernel_tick.py) |
| `argv[0]` 指不存在路徑，在執行時成 child127 | add 對含 `/` 的不存在 argv[0] 事先拒絕，根本不進 queue | [aos_kernel_add.py:103](../../proto4-3/aos_kernel_add.py) |
| 普通檔案是 aos-exec 合法目標 | daemon add 只收 `.json`；kernel add 讀的是 JSON 內容 | [aos_daemon_entry.py:50](../../proto4-3/aos_daemon_entry.py) |

proto5 的依據為 [inst-posix.md:79](../spec/inst-posix/fields.md)、[inst-posix.md:176](../spec/inst-posix/directives.md)、[inst-posix.md:244](../spec/inst-posix/exec.md)。

**4.5 不構成衝突的邊界**

| 項目 | 事實 |
|---|---|
| 100＝完成、101＝等待 | proto5 明確把它們留給 kernel／程式約定，不屬 inst 格式。[inst-posix.md:253](../spec/inst-posix/README.md) |
| 126／127 算 child，kernel 可累計一般失敗 | 與 proto5 的執行器語意相容 |
| daemon／kernel 的 config、state、request JSON 不解指示詞 | 它們目前只是直接 `json.load()`；不能把 inst 的指示詞允許位置直接外推成所有控制 JSON 的既有能力 |
| daemon `ok/result` 與 kernel `ok/msg` | 是兩套現在不同的檔案協議，不是同一 schema 的別名 |
| daemon done、kernel syscall done、LLM request done、LLM result | 四者含義不同：daemon 動作受理回應、kernel handler 回應、LLM 原請求歸檔、模型／排程結果 |
| 原子 rename | 各 writer 的單檔發佈方式；目前不存在橫跨上述檔案的統一交易、exactly-once 或崩潰對帳協議 |