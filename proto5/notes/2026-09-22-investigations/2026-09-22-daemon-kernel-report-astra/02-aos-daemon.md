← [daemon／kernel 調查報告（astra）](../2026-09-22-daemon-kernel-report-astra.md)（分檔 2/6）｜[上一份](01-aos-run.md)｜[下一份](03-aos-kernel-入口到退出碼.md)

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

來源：[aos_home.py:20](../../../../proto4-3/aos_home.py)、[aos-daemon:36](../../../../proto4-3/aos-daemon)。

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

來源：[aos_home.py:28](../../../../proto4-3/aos_home.py)、[aos_home.py:59](../../../../proto4-3/aos_home.py)、[aos_daemon_req.py:56](../../../../proto4-3/aos_daemon_req.py)、[aos_daemon_lifecycle.py:19](../../../../proto4-3/aos_daemon_lifecycle.py)。

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

來源：[aos_daemon_entry.py:67](../../../../proto4-3/aos_daemon_entry.py)、[aos_daemon_entry.py:94](../../../../proto4-3/aos_daemon_entry.py)、[aos_daemon_lifecycle.py:15](../../../../proto4-3/aos_daemon_lifecycle.py)。

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

來源：[aos_daemon_entry.py:40](../../../../proto4-3/aos_daemon_entry.py)、[aos_daemon.py:51](../../../../proto4-3/aos_daemon.py)。

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

來源：[aos_daemon_req.py:28](../../../../proto4-3/aos_daemon_req.py)、[aos_daemon_req.py:56](../../../../proto4-3/aos_daemon_req.py)。

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

來源：[aos_daemon.py:84](../../../../proto4-3/aos_daemon.py)、[aos_daemon_entry.py:118](../../../../proto4-3/aos_daemon_entry.py)。

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

來源：[aos_daemon_lifecycle.py:19](../../../../proto4-3/aos_daemon_lifecycle.py)、[aos_daemon.py:185](../../../../proto4-3/aos_daemon.py)、[aos_daemon_entry.py:166](../../../../proto4-3/aos_daemon_entry.py)、[aos_exec.py:190](../../../../proto4-3/aos_exec.py)。

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

來源：[aos_daemon_ctl.py:44](../../../../proto4-3/aos_daemon_ctl.py)、[aos_daemon_ctl.py:118](../../../../proto4-3/aos_daemon_ctl.py)、[aos_daemon_ctl.py:167](../../../../proto4-3/aos_daemon_ctl.py)。

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

既有測試確認 key、十二個 entry 欄位、五態、force、restart、CLI 生命周期與正常停止清理。**沒有建立崩潰復原、請求交易、PID 重用或跨 session 子孫清理保證。** 見 [test_daemon.py:74](../../../../proto4-3/test/test_daemon.py)、[test_daemon_ops.py:14](../../../../proto4-3/test/test_daemon_ops.py)、[test_daemon_cli.py:98](../../../../proto4-3/test/test_daemon_cli.py)。

---

