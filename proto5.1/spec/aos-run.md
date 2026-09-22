# aos-run：反覆跑同一個目標

← [README](../README.md)｜格式：[run-home](run-home.md)｜一次執行：[exec](exec.md)｜實作：[aos_run.py](../lib/aos_run.py)

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

## 程式：一次迴圈與寫入保證

安裝 SIGTERM／SIGINT handler 後發布初始快照。帶 `--home` 時記住啟動的 `os.getppid()`，
每圈及間隔／hold 的等待步進都比對；父 PID 變了便請本次做完後停止，不再開下一次，
避免 daemon 死後 runner 繼續跑。這項父程序檢查即使開 kill-tree 也不砍當次工作。
每次間隔結束先讀 ctl，再決定是否執行；第一次執行前也先讀。stop 正常退出。
hold 期間固定睡 50 ms 再看，跟 interval 無關，interval=0 也不忙轉。
held 只在值變化時寫快照；解除 hold 並決定開跑時寫 held=false，閒置 hold 不反覆改 run.json。

**保證每次順序：先發布 busy=true、target=null → 才讀／解析目標路徑 → 在讀 inst 之前發布
該目標的絕對路徑 → 跑 → 發布 busy=false、runs 加一，並把本次 target 存成 last_target、更新其他 last_*。**
符號連結先固定成實際路徑，公布與讀 inst 用同一路徑；中途換掉原連結不會使實際工作跟 target 不同。
資料夾目標公布的是選定的 inst 路徑。選定目標失敗仍按 kind／code 完成當次紀錄。

kernel 先換掉 CPU 目標檔，再看各 runner 的 run.json。若某支已取到舊行程 X，
它必定先寫過 busy，因此快照會是 busy 且 target=X 或尚未確定的 null；kernel 便不把 X 排去別顆。
若 runner 尚未開始讀目標，它之後只會取到換過的新目標。具體排程見 [aos-kernel](aos-kernel.md)。

完成後依序判斷訊號、usage、stop-exit、max-runs，沒停止才等 interval。
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
