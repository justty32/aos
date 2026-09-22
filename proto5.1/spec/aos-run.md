# aos-run：反覆跑同一個目標

← [README](../README.md)｜一次執行：[exec](exec.md)｜實作：[aos_run.py](../lib/aos_run.py)

```text
aos-run [TARGET] [--interval-ms N] [--timeout-ms N] [--max-runs N]
        [--stop-exit CODE ...] [--home DIR] [--kill-tree]
```

TARGET 預設 `.`；檔案、JSON inst、資料夾的執行交給 `aos_exec.run_target()`。
每次重新選定目標、讀 inst，所以兩次之間可以換檔。串流與 exit 檔照 inst，
不注入環境變數。不接受 exec 的 `--dir-target`／`--stderr`／子程式參數。

| 旗標 | 預設／意思 |
|---|---|
| `--interval-ms N` | 1000；非負整數；每次完成後才算間隔，0 立即下一次 |
| `--timeout-ms N` | 0 不限；非負整數；每次執行各自的毫秒期限 |
| `--max-runs N` | 0 不限；非負整數；每次 run_target 回傳都算一次，包括 kind=aos |
| `--stop-exit CODE` | 可重複；0～255；當次對外退出碼命中任一個便停止，kind=aos 換成 125 |
| `--home DIR` | 可省；指定後建立家、寫 run.json、讀 ctl.json；沒給就不寫狀態、不讀控制檔 |
| `--kill-tree` | 預設不開；第一次停止訊號就由 exec 終止子程式與當時找得到的後代 |

## 家：檔案格式

```text
R/
  run.json
  ctl.json       # 控制者有需要才寫
```

兩份 JSON 都是字面值。run.json 由 runner 寫同目錄唯一 `.tmp`，再 rename；
讀者不會讀到半份 JSON，沒有 fsync，不承諾斷電持久化。一個家只供一支 runner 使用。

```json
{"pid":1234,"busy":false,"target":"/abs/procs/a.json","runs":3,
 "last_exit":0,"last_kind":"child","last_ms":42,"held":false}
```

run.json 固定八格：pid 是 runner 的 PID；busy 是不是正在嘗試跑一次；target 是選定的絕對目標路徑；
runs 是已完成的次數；last_exit／last_kind／last_ms 是上次完成的對外碼、種類與耗時毫秒；
held 是不是被 hold 擋住。啟動時 busy=false、target=null、runs=0、三個 last_* 都 null、held=false。
last_kind 之後是 child／aos／usage；last_ms 是非負整數。busy=false 時保留剛完成的 target。
停止後保留最後快照；PID 存在不代表 runner 還活著。

ctl.json 只認一個 op：

```json
{"op":"hold"}
```

`stop`：不再開下一次，正常退出，停止原因是 ctl。
`hold`：不跑、寫 held=true，每個 interval 再看一次；檔案不見或 op 不再是 hold 就解除。
壞 JSON、非物件、未知 op 或讀不到，當沒有控制命令。
runner 不刪 ctl.json；誰寫誰刪。控制者也應原子替換，避免半份檔案被當作沒有。

## 程式：一次迴圈與寫入保證

安裝 SIGTERM／SIGINT handler 後發布初始快照。每次間隔結束，先讀 ctl，再決定是否執行。
第一次執行前也先讀 ctl。hold 解除並決定開跑時寫 held=false。

**保證每次順序：先發布 busy=true、target=null → 才讀／解析目標路徑 → 在讀 inst 之前發布
該目標的絕對路徑 → 跑 → 發布 busy=false、runs 加一與 last_*。**
符號連結先固定成實際路徑，公布與讀 inst 用同一路徑；中途換掉原連結不會使實際工作跟 target 不同。
資料夾目標公布的是選定的 inst 路徑。選定目標失敗仍按 kind／code 完成當次紀錄。

kernel 先換掉 CPU 目標檔，再看各 runner 的 run.json。若某支已取到舊行程 X，
它必定先寫過 busy，因此快照會是 busy 且 target=X 或尚未確定的 null；kernel 便不把 X 排去別顆。
若 runner 尚未開始讀目標，它之後只會取到換過的新目標。具體排程見 [aos-kernel](aos-kernel.md)。

完成後依序判斷訊號、usage、stop-exit、max-runs，沒停止才等 interval。
停止原因分別是 signal／usage／stop-exit／max-runs；ctl 的 stop 是 ctl。
這些原因只描述停止流程，不另加狀態欄位或事件通道。
kind=aos 的 library code 1 正規化成 125；普通 child 125 仍是 child。
正常停止回 0；CLI 用法錯、target kind=usage 或狀態 I/O 失敗回 2。
inst 讀驗失敗仍可下一次重試。狀態寫入失敗不再開下一次，stderr 一行 ReadFailed。

## 程式：訊號與 timeout

預設第一次 TERM／INT 只記「這次完成就停」，不砍子程式；第二次才 TERM 直接子程式的
process group，不查後代。其他 session 的工具或孫程式可繼續活著；第二次也沒有額外 KILL 計時器。
間隔或 hold 期間收到第一次訊號就停止。訊號落在啟動子程式前後也套同一規則。

開 `--kill-tree` 時，第一次 TERM／INT 就走 `aos_exec.terminate`：Linux 先從 `/proc`
快照子程式與後代的 process groups，一起 TERM，最多兩秒後 KILL、收直接子程式。
父程式先退出也不忘記已快照的後代。重複訊號不重做快照、不延長寬限。
其他 POSIX 沒有 `/proc` 時只處理原 group；事前已脫離親子樹、或快照後新生並脫離原 group
的程序不在保證內。這不是 cgroup，也不追捕任意 daemon。

每次 timeout 沿用 exec 的終止流程，跟 kill-tree 旗標無關；真正 timeout 不會自動停止 runner，
沒有其他停止條件命中就繼續下一次。主動訊號不冒充 timeout。
