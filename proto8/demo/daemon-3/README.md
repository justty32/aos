# daemon-3：一次性的東西掛 daemon 的兩種寫法（10-30）

← [demo](../README.md)｜程式：[aos-daemon § execs](../../impls/aos-daemon/README.md)｜設計：[thinking 10-30 agent-lifecycle](../../thinking/2026-10-30-agent-lifecycle.md) 結論 B-12、實作第 8 步；條文：[N-28 的 10-30 補（`execs`）、N-54 的 10-30 補（`execs_added`／`execs_removed`）](../../docs/NORMS/04-基礎設施-loop與daemon.md)

要跑一次就結束的東西（例：一隻射後不理的 agent、`claude -p` 的腳本）想讓 daemon 管著（看得到死活、收得掉），有兩種寫法。這個 demo 用同一支小程式 [`demo/tick`](../tick/)（aos-loop 跑 5 次 aos-tick，時鐘檔 `$AOS_STACK/tick.txt` 走到 5；離線、不接腦）各掛一次：

```json
{"interval_ms": 200, "max": 10, "ctl": "daemon_ctl.json", "state": "daemon_state.json", "loops_ctl_mailbox": "loops_ctl_mailbox",
 "loops": {"tick_loop": {"exec": "../tick", "max": 1}},
 "execs": {"tick_exec": "../tick"}}
```

| 寫法 | 怎麼寫 | daemon 怎麼起 | 小格裡有什麼 | 列在 |
|---|---|---|---|---|
| ① 包成 `max: 1` 的子 loop（使用者 10-30「包成max:1也是可以」；現況就能用） | `"loops": {"名字": {"exec": 目標, "max": 1}}`（**一定要寫 `max: 1`**，沒寫＝退 0 就再跑一次） | 起一支 aos-loop，它再 `aos-exec 目標` 一次 | `loop.json`（daemon 寫的）、`state.json`（外層 aos-loop 的窗）、`stderr.txt`、程式自己的檔 | `loops_state.json` 的 `loops` |
| ② exec 型子項（使用者 10-30「讓daemon可以掛aos-exec，也是不錯的」） | `"execs": {"名字": 目標}` 或 `{"名字": {"exec": 目標}}`；目標＝aos-exec 的目標（字串或 `[目標, 參數...]`），11-02 晚起也收 `{"exec": 內嵌單子}`（daemon 寫成小格的 `exec.json` 跑一次） | 直接 `aos-exec 目標` 一次，不包 aos-loop | `stderr.txt`、程式自己的檔（沒有 `loop.json`、`ctl.json`、`state.json`；單子才多一份 `exec.json`） | `loops_state.json` 的 `execs` |

兩種都是：小格 `$AOS_STACK/loops/<名字>/`（11-02 改 `loops/<名字>/`，[thinking 11-02 stack-tools](../../thinking/2026-11-02-stack-tools.md)）、`AOS_STACK`＝小格、stdin 接 `/dev/null`、stderr 附加到小格的 `stderr.txt`、自成一個行程群組；退了＝`done`、記 `code`／`signal`（daemon 的 log，`--enable-logs` 才印）、**不重起**，11-02 起從表上拿掉（原本「列留著直到名單拿掉」＝10-30 方向題 2，使用者 11-02 改成「子項結束後不留名單」）；停＝名單拿掉（`loops_removed`／`execs_removed`）或 daemon 收工：SIGTERM，10 秒不退 SIGKILL 整群。差別：① 多一層 aos-loop（`ps` 看得到它），而且外層 loop 的 `state.json` 在小格裡——掛進去的程式自己也開 `state.json` 窗的話兩個 loop 寫同一份檔（N-28 開頭 ②），得把裡面那層的窗改名或不開；② 少一層行程，SIGTERM 直接打到那支程式。`execs` 與 `loops` 共用名字空間（同一個名字兩邊都寫＝`CfgBad`）。

| 檔 | 做什麼 |
|---|---|
| `_entry` | `exec aos-daemon "$@" daemon.json`（後面的參數原樣給 daemon，例 `--max 50`） |
| `daemon.json` | 上面那份：`max` 10、`interval_ms` 200（約 2 秒收工）；開信箱（`loops_ctl_mailbox`，11-02 晚原 `loops_mailbox`；下面「半路加一個」用 aos-daemon-ctl 投信）；`loops` 的 `tick_loop`（①）、`execs` 的 `tick_exec`（②）都指 `../tick`（相對路徑從 daemon 的 cwd＝`demo/daemon-3/` 算） |

## 怎麼跑

PATH 要有 aos-exec、aos-loop、aos-daemon、aos-post（C++，`proto8/impls/<名>/bin/`，先建，見 [testing](../../../wf/workflows/testing.md)）與 aos-tick、aos-daemon-ctl（`proto8/bin/`）。在一個空的工作區裡：

```sh
R=~/repo/simple_tools/aos/proto8
export PATH=$R/bin:$R/impls/aos-exec/bin:$R/impls/aos-loop/bin:$R/impls/aos-daemon/bin:$R/impls/aos-post/bin:$PATH
ws=$(mktemp -d); cd $ws
aos-exec $R/demo/daemon-3; echo "結束碼 $?"     # 約 2 秒；stack 在 $ws/.stack/
cat .stack/loops_state.json
find .stack -type f | sort
```

## 跑一次的結果（10-30 WSL）

結束碼 0。`.stack/loops_state.json`（pid、時間每次不同；11-02 起兩個跑完就從表上拿掉、kind／recorded_at 收掉、`letter_warning` 改名 `mailbox_warning`）：

```json
{"ctl_seq": null, "ctl_warning": null, "mailbox_warning": null, "loops": {}, "execs": {},
 "pid": 135520, "started_at_ticks": 778245, "boot_id": "…", "updated_at": "2026-10-30T02:03:32.502+00:00"}
```

`aos-exec $R/demo/daemon-3 --enable-logs` 才看得到兩個的結束碼（stdout 一行一個：`{"at", "name": "tick_loop", "table": "loops", "phase": "done", "pid", "code": 0, "signal": null}`，`tick_exec` 同樣在 `execs`）。

`find .stack -type f | sort`（11-02 起子項小格在 `.stack/loops/<名字>/`，下面照新路徑改了；10-30 那次是 `.stack/<名字>/`）：

```
.stack/daemon_state.json
.stack/loops/tick_exec/stderr.txt
.stack/loops/tick_exec/tick.txt
.stack/loops/tick_loop/loop.json
.stack/loops/tick_loop/state.json
.stack/loops/tick_loop/stderr.txt
.stack/loops/tick_loop/tick.txt
.stack/loops_state.json
```

兩格的 `tick.txt` 都是 `5`、`stderr.txt` 都是空的；`tick_loop/loop.json`＝`{"exec": "<絕對路徑>/demo/daemon-3/../tick", "max": 1, "ctl": "ctl.json", "state": "state.json", "_entry": ["aos-loop", {"$env": "AOS_CF"}]}`（daemon 補的 ctl／state 與 `_entry`）。`tick_exec/` 只有 stderr 與程式自己的時鐘檔。

## 半路加一個（aos-daemon-ctl）

`aos-exec XXX`＝掛到 Linux 的 proc 管理；`aos-daemon-ctl add XXX`＝掛到 daemon 上（[bin/README](../../bin/README.md)）。它往 daemon 的信箱投一封 `loops_added`／`execs_added` 的信（N-54 的手把；所以這份 daemon.json 開了信箱 `loops_ctl_mailbox`）。哪個 daemon＝`--daemon-stack` ＞ `$AOS_DAEMON_STACK`（daemon 的 `$AOS_STACK`）。XXX 有 `loop.json`＝掛成 loop 子項（子 loop 直接跑它的 loop.json）、沒有＝掛成 `execs`（11-02 `--kind` 拿掉，使用者「把--kind刪掉」；exec 型可接 `XXX -- 參數...`，loop 型帶參數＝ArgumentsBad）。

```sh
aos-exec $R/demo/daemon-3 --max 50 &       # 約 10 秒
export AOS_DAEMON_STACK=$ws/.stack
until [ -d $AOS_DAEMON_STACK/loops_ctl_mailbox/new ]; do sleep 0.1; done
aos-daemon-ctl add $R/demo/tick                               # tick 有 loop.json＝loop 型、名字 tick；印信號
aos-daemon-ctl add --name tick2 $R/demo/tick                  # 同一個再掛一隻、換名字
sleep 1; aos-daemon-ctl ls
aos-daemon-ctl rm tick2; sleep 1; aos-daemon-ctl ls
wait; echo "結束碼 $?"
```

第一次 `ls`（名字、種類、phase、pid、code；pid 每次不同）。11-02 起跑完的子項不留在表上，tick 跑 5 次（約 1.5 秒）就結束，所以 `sleep 1` 時看得到的是還在跑的那幾個（10-30 那次的 `done` 列不會再出現）：

```
tick	loop	running	135580	-
tick2	loop	running	135581	-
```

`rm tick2` 之後那一列不見了（已經自己跑完的話本來就不在）；結束碼 0。

`run.sh` 的 daemon-3 段跑上面「怎麼跑」那次、印 stack 樹；自動測：`impls/aos-daemon/tests/test_demo.py`（`run_daemon3`）。
