# aos-run：反覆跑同一個目標

← [README](../README.md)｜一次執行：[exec](exec.md)｜實作：[aos_run.py](../lib/aos_run.py)

```text
aos-run [TARGET] [--interval-ms N] [--timeout-ms N] [--max-runs N]
        [--stop-exit CODE ...] [--status-fd N]
```

TARGET 預設 `.`，三種目標完全交給 `aos_exec.run_target()`。每次重新讀 inst，因此可以換檔。
沒有家目錄或狀態檔，不注入環境變數；串流與 exit 檔照 inst。只有上列旗標，不接受 exec 的
`--dir-target`／`--stderr`／子程式參數；需要的設定寫進 inst。

| 旗標 | 預設／意思 |
|---|---|
| `--interval-ms N` | 1000；非負整數；每次完成後才開始算間隔，0 立即下一次 |
| `--timeout-ms N` | 0 不限；非負整數；每次執行各自的毫秒期限 |
| `--max-runs N` | 0 不限；非負整數；每次 run_target 回傳都算一次，包括 kind=aos |
| `--stop-exit CODE` | 可重複；0～255；當次對外退出碼命中任一個便停止，kind=aos 換成 125 |
| `--status-fd N` | 已開好的可寫 fd；沒有就不發事件；觀察者關閉後停止發送、執行照舊 |

## 一次迴圈與事件

先安裝 SIGTERM／SIGINT handler，再送 `ready`。每次執行之前送 start，回傳之後送 done，
判斷停止條件，否則等完成後間隔。編號從 1 起，每行一個 ASCII 事件：

```text
ready
start #1
done #1 exit=0 kind=child
stop max-runs
```

kind 原樣是 child／aos／usage；kind=aos 的函式庫碼 1 換成 exec 的對外碼 125。
reason 是 signal／max-runs／stop-exit／usage。
判斷順序為已收到訊號、usage、stop-exit、max-runs。子程式失敗不等於 run 失敗：正常停止
回 0，CLI 用法或 target 的 kind=usage 回 2。inst 讀驗失敗 kind=aos 仍可下一次重試。

## 第一次 TERM 就砍到底

第一次 SIGTERM（SIGINT 同義）標記停止，立即由 `aos_exec.terminate(popen)` TERM 當前子程式
的 process group；共用 exec 等最多 2 秒後 KILL，收完才送 done／stop，永不再開下一次。
間隔或等槽鎖時收到訊號則直接停止。重複訊號不改期限、不另設第二次訊號行為。
每次 timeout 使用同一個終止實作，但沒有停止條件命中時仍會下一次。

tool CPU／agent 跑工具的 `run_inst` 會再 setsid，單一 killpg 到不了。Linux 上終止前從 `/proc`
快照當前子程式後代的 process groups，整批 TERM，再在同一個 2 秒期限 KILL；直接父行程
先退出仍處理後代。其他 POSIX 沒有 `/proc` 時只處理原 group。這不是沙箱：已脫離親子樹、
或終止開始後才另生 session 的程式不在快照保證內；不追捕任意 daemon。

## kernel 的換槽協定

kernel 預先建立 `cpus/<n>.json.lock`；aos-run 若看見 `TARGET.lock`，每次用同一個 inode 的
flock 排他鎖包住 start、讀／執行 target、done。等鎖採非阻塞重試，TERM 仍可立即停止。
kernel 也拿這把鎖才能換檔，避免 daemon 的 `running=false` 快照過期之後舊 inst 又開跑。
interval 很短時，單靠碰巧讀到 `running=false` 會讓排隊行程飢餓。因此 kernel 要換人時先把
同一鎖檔的首 byte 寫成 `Y`。這是內部讓位標記，不會打斷已開始的 invocation；aos-run
下一輪拿鎖後讀到 `Y`，就解鎖並可中止地等候，直到 kernel 在鎖內清空標記。kernel 下一格
便可取得穩定的 `running=false`，拿鎖、remove 等 runner 停妥、清標記與換檔、再 add。
等標記期間沒有 start 事件，TERM 立即正常停止。普通空鎖檔照常執行。
鎖檔不得 replace 或 unlink。沒有 sidecar 的普通 target 不建檔、不加鎖。
