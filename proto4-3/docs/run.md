# proto4-3／aos-run
← [README](../README.md)

## aos-run：一直跑同一個目標

```sh
aos-run xxx [--dir-target REL] [--timeout-ms N] [--interval-ms N] [--from-start]
            [--max-runs N] [--time-limit-ms N] [--stop-exit CODE]...
            [--status-fd N] [--stop-on-error]
```

[proto4 筆記第 12 節](../../proto4/notes/2026-09-08-ideas.md)的原型。**執行那一段完全不重寫**：
就是反覆叫 `aos_exec.run_target()`，`xxx` 是哪三種目標、退出碼怎麼來，通通照上面 aos-exec
那幾節。aos-run 只管三件事——下一次什麼時候開始、什麼時候停、跑完印一行。

**時間旗標一律是毫秒整數**，跟 aos-exec 的 `--timeout-ms` 同一個單位。

| 旗標 | 預設 | 意思 |
|---|---|---|
| `--dir-target REL` | `.aos/inst.json` | 同 aos-exec，原樣傳給 `run_target()` |
| `--timeout-ms N` | `0`＝不限 | **每一次**執行的上限，原樣傳給 `run_target()` |
| `--interval-ms N` | `1000` | 兩次執行之間的間隔 |
| `--from-start` | 沒有＝從結束算 | 間隔改從上一次**開始**的時刻算 |
| `--max-runs N` | `0`＝不限 | 跑滿 N 次就停 |
| `--time-limit-ms N` | `0`＝不限 | 從 aos-run 起跑算的整體時限（**硬的**） |
| `--stop-exit CODE` | 沒有 | 某一次的退出碼是 CODE 就停，可以給很多次 |
| `--status-fd N` | 沒有＝不寫 | 往這個 fd 寫事件（給程式看的，見下面） |
| `--stop-on-error` | 沒有＝不停 | 某一次是 **aos-exec 自己失敗**（`kind=aos`）就停 |

### 間隔從哪裡算

`--interval-ms 5000`、某一次跑了 1.2 秒：

| | 下一次什麼時候開始 |
|---|---|
| 預設（從上一次**結束**算） | 第 **6.2** 秒 |
| `--from-start`（從上一次**開始**算） | 第 **5** 秒 |

`--from-start` 時一次跑超過 interval（例如 interval 5 秒、跑了 7 秒），下一次**立刻**開始，
**不補跑**錯過的格：下一次的起點是 `max(現在, 上次起點 + interval)`。長跑會慢慢往後漂
（因為是「上次起點＋interval」不是「起跑＋n×interval」），要對齊格子之後再說。

計時用 `time.monotonic()`，改系統時間不影響。

### 給程式看的：`--status-fd N`

stderr 那些 `aos-run: …` 行是**給人看的**，照舊印。`--status-fd N` 是**給程式看的**
（aos-daemon 讀的就是它，不再去解 stderr）：一行一個事件、`\n` 結尾、寫完就到。

```
ready                                 裝好訊號處理器了、第一次還沒開跑
start #1                              第 1 次要開跑了
done #1 exit=0 kind=child 0.3s        第 1 次跑完了（kind 見 aos-exec 那節）
done #2 exit=125 kind=aos 0.0s        第 2 次：aos-exec 自己失敗（inst.json 壞／沒出現）
stop max_runs                         停了；然後這個 fd 就關掉
```

`kind=aos` 那種的 `exit=` 一律報 **125**（跟 aos-exec 命令列的退出碼同一個數字），所以
「aos 自己失敗」跟「子程式回 1」在這條流上分得開。

沒給 `--status-fd` 就什麼都不寫。寫失敗（對方把管子關了）＝忽略，不影響執行——回報狀態
不該把工作弄倒。`ready` 特別重要：daemon 靠它知道「訊號處理器裝好了，現在 SIGSTOP／
SIGTERM 送得過去」。

### 什麼時候停

五個條件，任一成立就停；退出碼多數是 **0**，兩個例外：

| 原因 | 什麼時候 | 退出碼 |
|---|---|---|
| `max_runs` | 跑滿 `--max-runs N` 次 | 0 |
| `time_limit` | 撞到 `--time-limit-ms`。**硬時限**：正在睡→醒來就退；正在跑→**那次被砍** | 0 |
| `stop_exit` | 某一次的退出碼在 `--stop-exit` 那組裡面 | 0 |
| `error` | 給了 `--stop-on-error`，而且某一次 `kind` 是 `aos`（aos-exec 自己失敗） | **125** |
| `signal` | 收到**第一次** SIGTERM／SIGINT | 0 |
| `signal_forced` | 同一個訊號又收到**第二次**（腰斬正在跑的那次） | 128+N（SIGTERM＝143、SIGINT＝130） |

`signal_forced` 退出碼不是 0：**第二次代表有工作被腰斬，不算乾淨**。

**硬時限怎麼砍正在跑的那次**：不另開執行緒，而是每次呼叫 `run_target()` 時把 `timeout_ms`
換成 `min(原本的或無限, 剩下的毫秒)`，交給 aos-exec 本來就有的那套砍法（SIGTERM 整個
process group、2 秒、SIGKILL），所以被砍那次印出來的碼是 143 或 137。

**訊號**：第一次 SIGTERM／SIGINT ＝ 讓正在跑的那次**跑完**再退，退出碼 0；第二次**同一個**
訊號 ＝ 直接 SIGKILL 掉正在跑的那個 process group 再退，退出碼變 128+N。睡覺是小步睡的
（0.05 秒一步），所以 `--interval-ms 5000` 睡到一半也叫得醒，不會不理你五秒。

**aos-exec 自己失敗（inst.json 壞掉）預設不算停止條件**，照 interval 一直試——壞了也活著，
跟 proto4-2 的 cpu 一樣。要它停就給 `--stop-on-error`（退出碼 125）。

### 印什麼、回什麼

不寫檔。每跑完一次，在 **aos-run 自己的 stderr** 印一行（秒數一位小數）：

```
aos-run: #1 exit=0 0.3s
aos-run: #2 exit=1 0.0s
aos-run: stop max_runs
```

那個 `exit=` 是 `run_target()` 回的 code，只有一個地方不是原樣：**aos-exec 自己失敗
（`kind=aos`）一律報 125**，跟子程式自己回的 1 分得開。要看是誰的碼就看 status-fd 那條的
`kind=`。

aos-run 自己的退出碼：**2**＝用法錯（旗標不認得、沒給 `xxx`、`xxx` 是不存在的**非**
`.json` 路徑、時間／次數旗標是負數）；**0**＝`max_runs`／`time_limit`／`stop_exit`／第一次訊號（`signal`）；
**125**＝`--stop-on-error` 撞到 aos-exec 自己失敗（`error`）；**128+N**＝同一個訊號收到
第二次（`signal_forced`，正在跑的那次被腰斬）。子行程的退出碼只出現在那些 `#n exit=`
行裡，不會變成 aos-run 的退出碼。

`xxx` 只在起跑前檢查一次，而且**以 `.json` 結尾的路徑連這一次都不查**（不存在就每次回
`exit=125 kind=aos`，檔案出現了就跑起來——daemon 靠的就是這條）。資料夾跑到一半被搬走，
之後每次就是 `run_target()` 回 `kind=usage` 的那行，迴圈照樣繼續——**`--stop-on-error`
只看 `kind=aos`，不管 `usage`**（資料夾被人搬走是外面的事，不是這份 inst.json 壞了）。

當成函式用（daemon 之後就是這樣接）：

```python
import aos_run
code, reason = aos_run.run_loop("/path/to/folder", interval_ms=5000, max_runs=10,
                                from_start=True, status_fd=w, stop_on_error=True)
```

