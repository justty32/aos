# proto4-3／aos-daemon
← [README](../README.md)

## aos-daemon：一個 dict，key＝一份 inst.json 的路徑，value＝正在跑的 aos-run

[proto4 筆記第 13 節](../../proto4/notes/2026-09-08-ideas.md)的原型（key 那條照
[第 15 節](../../proto4/notes/2026-09-08-ideas.md)改過）。**daemon 就是一個常駐進程，裡面
一個 dict**——key 是**那份 inst.json 的路徑**，value 是一個正在跑的 `aos-run` 子進程，
一份 inst.json 最多一個。value 是**子進程**不是執行緒，所以進程的事通通交給 Linux：暫停＝SIGSTOP、
繼續＝SIGCONT、刪＝SIGTERM。

**`aos-daemon` 是一支普通程式，你自己開著它、自己管它的生死**（要放背景 `aos-daemon &`、
tmux、systemd 都行，aos 不管）；**`aos-daemon-ctl` 是另一支對它下指令的工具**，兩支分開。

```sh
./aos-daemon &                                               # 普通前台程式，自己丟去背景

./aos-daemon-ctl add /path/to/inst.json --interval-ms 2000   # 旗標原樣傳給 aos-run
./aos-daemon-ctl add /path/to/other.json --interval-ms 500   # 同資料夾第二份＝另一筆
./aos-daemon-ctl ls
./aos-daemon-ctl pause /path/to/inst.json
./aos-daemon-ctl resume /path/to/inst.json
./aos-daemon-ctl rm /path/to/inst.json --force
./aos-daemon-ctl stop                                        # 請 daemon 收工、進程退出
```

### key＝那份 inst.json 的路徑

**key 就是那個 `.json` 檔的 realpath**（[§15](../../proto4/notes/2026-09-08-ideas.md)），
所以 symlink、`..`、相對路徑寫法通通算同一筆。同一個 key 第二次 `add`＝`ok:false`、
**舊的不動**；**同一個資料夾可以掛好幾份不同的 inst.json，各自一支 aos-run**。

| 你給的路徑 | 收不收 |
|---|---|
| `.json` 檔 | **收** |
| `.json` 路徑但檔案**還不存在** | **收**——aos-run 每次跑回 `exit=125 kind=aos`，檔案出現了就自然跑起來 |
| 資料夾（連名字叫 `x.json` 的資料夾也是） | 拒絕：「只收 .json 檔，這是資料夾：…」 |
| 普通檔案（副檔名不是 `.json`） | 拒絕：「只收 .json 檔：…」 |

`add`／`restart` 照上表擋；`rm`／`get`／`pause`／`resume` 不擋，存不存在都照 realpath
查表（表上有就找得到）。**不拿 inst.json 裡的 `cwd` 欄位當 key**——那個每次執行都可能被
改，還可能是 `$ref` 解出來的。

`aos-daemon-ctl` 的 `add`／`restart` **不收 `--dir-target`**（那是給資料夾當目標用的，
這裡的目標一定是一份 `.json`）：寫了就是用法錯、退出碼 2，不會被偷偷吞掉。daemon 開
aos-run 時也不會加這個旗標。`aos-run`／`aos-exec` 單獨用時照舊有這個旗標。

### 五個狀態

每一筆有一個 `state`，`get`／`ls`／`state.json` 都帶著它：

| `state` | 意思 |
|---|---|
| `running` | 正常跑著 |
| `pause_pending` | 收到 `pause` 了，**等它睡著**才會真的 SIGSTOP |
| `paused` | 已經 SIGSTOP 住了 |
| `stopping` | 送過 SIGTERM 了，等它自己退（5 秒還不退＝SIGKILL 整個 group） |
| `restarting` | 跟 `stopping` 一樣，只是收屍之後要用新旗標同 key 再開一顆 |

### 七個動作：全部立刻回，等待是主迴圈的事

**主迴圈不等任何人。** 七個動作都是「送個訊號、標個狀態、立刻回 `(ok, result)`」，真正的
「等它退」「等它睡著」交給每 0.2 秒跑一次的那一圈。所以 `rm` 一個手上那次要跑一小時的
aos-run，daemon 照樣立刻收下一個請求——只有收工（`stop`）會同步等，那時候本來就該等。

| 動作 | 做什麼 | 回什麼 |
|---|---|---|
| `add` | 先擋掉資料夾／非 `.json`，再開一個 `aos-run FILE.json 旗標… --status-fd N` 子進程（`start_new_session`），記進表 | 那一筆 |
| `remove` | 暫停中的先 SIGCONT → SIGTERM → 標 `stopping`、記 5 秒的 deadline。`force`＝0.2 秒後再補一發 SIGTERM（腰斬，退出碼 143）。過了 deadline 還活著＝SIGKILL 整個 group | `"stopping"` |
| `restart` | 跟 `remove` 一樣送 SIGTERM，但標 `restarting`、把新旗標存在那一筆上；**收屍時**用新旗標同 key 再 `add`——aos-run 開跑後旗標改不了 | `"restarting"` |
| `get` | 一筆：`pid`／`target`／`args`／`started_at`／`state`／`ready`／`running`／`runs`／`last_exit`／`last_kind`／`last_line`／`alive` | 那一筆 |
| `ls` | 全部的 `get`，key 是那份 `.json` 的路徑 | 整張表 |
| `pause` | 標 `pause_pending`；主迴圈每圈看，`ready` 且 `running == False`（在睡覺）才送 SIGSTOP、改 `paused` | `"pause_pending"` 或 `"paused"` |
| `resume` | `paused`→SIGCONT、改 `running`；`pause_pending`→取消那個等待 | `"running"` |

**pause 不腰斬正在跑的那次**——等 aos-run 說它 `done` 了才停，所以暫停之後那份 inst.json
沒有做到一半的工作。代價：`interval` 極短時 SIGSTOP 可能剛好落在下一次開跑之後，那次會跑完才真的停，
**不保證從此零次**。已經 `paused`／`pause_pending` 的再 `pause`＝冪等；`stopping`／
`restarting` 的再 `rm`＝冪等 ok（`restarting` 途中改 `rm` 就不再重開）。

### 近況從哪來：讀 status-fd，不解 stderr

`add` 的時候開一條 `os.pipe()`，寫端用 `pass_fds` 交給子進程、命令列加
`--status-fd <寫端>`，daemon 這邊立刻關掉自己那份寫端（不然讀端永遠等不到 EOF），
**每一筆兩條執行緒**：

- **status 那條**逐行讀事件，更新 `ready`／`running`／`runs`／`last_exit`／`last_kind`／
  `last_line`。這是給程式看的，格式固定，不用猜。
- **stderr 那條**照舊逐行讀，原樣（前面加 key）append 進 `daemon.log`——純流水帳，
  **不再從這裡解近況**。

```
22:24:49 /tmp/w/inst.json aos-run: #1 exit=5 0.0s
22:24:49 /tmp/w/inst.json aos-run: stop max_runs
22:24:49 自己退了 /tmp/w/inst.json pid=223053 exit=0 last=stop max_runs
```

aos-run **自己退了**（`--max-runs` 跑滿、時限到、`--stop-exit`、被別人殺）→ daemon 收屍、
從表上拿掉、`daemon.log` 記一行。不自動重開；那份 inst.json 之後可以再 `add`。

### 請求格式

daemon 與外面之間只有檔案：寫一個 JSON 到 `H/requests/`（先 `.tmp` 再 rename），daemon
每 0.2 秒掃一次（`.tmp` 忽略），處理完搬到 `H/requests/done/` 同名、內容＝**原請求 ＋
`ok` ＋ `result`**。**daemon 自己讀請求**，不經過 kernel——kernel（往下看那一節）只是
另一個會叫 `aos-daemon-ctl` 的使用者，不碰 `requests/`。

```json
{"op":"add",     "target":"/path/to/inst.json", "args":["--interval-ms","2000"]}
{"op":"remove",  "target":"/path/to/inst.json", "force":false}
{"op":"restart", "target":"/path/to/inst.json", "args":["--interval-ms","5000"]}
{"op":"get",     "target":"/path/to/inst.json"}
{"op":"ls"}
{"op":"pause",   "target":"/path/to/inst.json"}
{"op":"resume",  "target":"/path/to/inst.json"}
{"op":"stop"}
```

目標欄位七個動作**一律叫 `target`**（舊的 `dir` 沒了），值是那份 inst.json 的路徑、先
realpath 再查表。不認得的 op、缺欄位、`add`／`restart` 給了資料夾或非 `.json`＝`ok:false`
（不是炸掉）；**`add` 的 `.json` 不存在不算錯**，照收。`stop`＝daemon 收工：所有 aos-run 送 SIGTERM、等它們退、自己退；daemon 收到
**SIGTERM 也一樣**。

### 家目錄

`--home H` → 環境變數 `AOS_DAEMON_HOME` → 預設 `~/.aos-daemon`。`aos-daemon` 與
`aos-daemon-ctl` 要指到同一個家才對得上話。

```
H/requests/         請求檔
H/requests/done/    處理完的
H/daemon.pid        daemon 的 pid
H/state.json        每 0.5 秒寫一次（先 .tmp 再 rename）
H/daemon.log        daemon 自己的話 ＋ 每個 aos-run 的 stderr（原樣，前面加 key）
```

`state.json` 就是 `ls` 的內容：

```json
{"pid": 223051, "home": "/tmp/myaos",
 "runs": {"/tmp/w/inst.json": {"pid": 223053, "target": "/tmp/w/inst.json",
                     "args": ["--interval-ms","200"],
                     "started_at": 1788963889.1, "state": "running", "ready": true,
                     "running": false, "runs": 3, "last_exit": 5, "last_kind": "child",
                     "last_line": "done #3 exit=5 kind=child 0.0s", "alive": true}}}
```

### CLI：aos-daemon 與 aos-daemon-ctl 分開兩支

```sh
aos-daemon [--home H]
```

普通的**前台程式**，不會自己背景化。跑起來就寫 `daemon.pid`、進主迴圈，直到收到
SIGTERM／SIGINT（Ctrl-C）或 `aos-daemon-ctl stop` 才收工。家裡已經有一個活著的 daemon
（`daemon.pid` 那個 pid 還活著）→ 印「已經在跑（pid N）」、退出碼 1，不會搶著跑。沒有
子命令；要放背景自己 `aos-daemon &`，或交給 tmux／systemd 之類的常駐管理員，aos 不管。

```sh
aos-daemon-ctl add FILE.json [aos-run 旗標…]|rm FILE.json [--force]
              |restart FILE.json [旗標…]|get FILE.json|ls
              |pause FILE.json|resume FILE.json|stop       [--home H]
```

**FILE 是一份 inst.json 的路徑**（不是資料夾），`--dir-target` 在這裡是用法錯（退出碼 2）。

| 指令 | 怎麼做的 |
|---|---|
| `stop` | 丟 `{"op":"stop"}` 請 daemon 收工，等 `daemon.pid` 的 pid 真的死掉才回（上限 10 秒） |
| `ls`／`get` | **直接讀 `state.json`** 印表（`FILE PID STATE RUNS LAST_EXIT`），不丟請求、不用等 daemon 回，所以看到的最多是 0.5 秒前的樣子；daemon 沒在跑時照樣印最後一份 state.json，但 stderr 提醒一句 |
| `add`／`resume` | 丟請求檔、等 `done/` 出現（上限 10 秒）、印 `ok`／`result`；`ok:false`＝退出碼 1 |
| `rm`／`restart`／`pause` | 同上，但因為 daemon 是「收到了、開始做」就回，**這裡再多等一步**（見下面） |

**`rm`／`restart`／`pause` 回來時事情已經做完了。** daemon 那邊回的是 `stopping`／
`restarting`／`pause_pending`，ctl 拿到之後**輪詢 `state.json`**（上限 10 秒）等到真的到位
才印結果、才退出：

| 指令 | 等到什麼 | 印 | 等不到 |
|---|---|---|---|
| `rm FILE.json` | 那個 key 從表上**消失** | `removed <key>` | 「等不到它退掉，還在表上」、退出碼 1 |
| `restart FILE.json …` | 那個 key 的 `pid` **換成新的**且 `state` 是 `running` | `restarted <key>` | 「等不到新的那顆起來」、退出碼 1 |
| `pause FILE.json` | `state` 變成 `paused` | `paused <key>` | 「還在等它睡著」、退出碼 1 |

等不到只是**這支 CLI 不等了**，daemon 那邊該做的還是會做完。

`daemon` 沒在跑時，`ls`／`get` 照上面讀最後狀態，其他指令直接印「daemon 沒在跑」、退出碼
1、不丟檔。`--home` 可以擺在任何位置，其他旗標**原樣**留給 aos-run（所以這支不用
argparse，不然 `--max-runs` 之類會被吃掉）。

