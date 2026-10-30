# daemon-3：一次性的東西掛 daemon 的兩種寫法（10-30）

← [demo](../README.md)｜程式：[aos-daemon § execs](../../impls/aos-daemon/README.md)｜設計：[thinking 10-30 agent-lifecycle](../../thinking/2026-10-30-agent-lifecycle.md) 結論 B-12、實作第 8 步；條文草稿「N-28 10-30 補：execs」「N-54 10-30 補」（正文還沒落）

要跑一次就結束的東西（例：一隻射後不理的 agent、`claude -p` 的腳本）想讓 daemon 管著（看得到死活、收得掉），有兩種寫法。這個 demo 用同一支小程式 [`demo/tick`](../tick/)（aos-loop 跑 5 次 aos-tick，時鐘檔 `$AOS_STACK/tick.txt` 走到 5；離線、不接腦）各掛一次：

```json
{"interval_ms": 200, "max": 10, "ctl": "ctl.json", "state": "state.json", "loops_mailbox": "loops_mailbox",
 "loops": {"tick_loop": {"exec": "../tick", "max": 1}},
 "execs": {"tick_exec": "../tick"}}
```

| 寫法 | 怎麼寫 | daemon 怎麼起 | 小格裡有什麼 | 列在 |
|---|---|---|---|---|
| ① 包成 `max: 1` 的子 loop（使用者 10-30「包成max:1也是可以」；現況就能用） | `"loops": {"名字": {"exec": 目標, "max": 1}}`（**一定要寫 `max: 1`**，沒寫＝退 0 就再跑一次） | 起一支 aos-loop，它再 `aos-exec 目標` 一次 | `loop.json`（daemon 寫的）、`state.json`（外層 aos-loop 的窗）、`stderr.txt`、程式自己的檔 | `loops_state.json` 的 `loops` |
| ② exec 型子項（使用者 10-30「讓daemon可以掛aos-exec，也是不錯的」） | `"execs": {"名字": 目標}` 或 `{"名字": {"exec": 目標}}`；目標＝aos-exec 的目標（字串或 `[目標, 參數...]`），單子物件不收（要跑單子就寫 `"daemon.json#/…"` 指進去） | 直接 `aos-exec 目標` 一次，不包 aos-loop | `stderr.txt`、程式自己的檔（沒有 `loop.json`、`ctl.json`、`state.json`） | `loops_state.json` 的 `execs` |

兩種都是：小格 `$AOS_STACK/<名字>/`、`AOS_STACK`＝小格、stdin 接 `/dev/null`、stderr 附加到小格的 `stderr.txt`、自成一個行程群組；退了＝`done`、記 `code`／`signal`、**不重起**，列留著直到名單拿掉（方向題 2，[決定（10-30）](../../thinking/2026-10-30-agent-lifecycle.md#決定10-30)）；停＝名單拿掉（`loops_removed`／`execs_removed`）或 daemon 收工：SIGTERM，10 秒不退 SIGKILL 整群。差別：① 多一層 aos-loop（`ps` 看得到它），而且外層 loop 的 `state.json` 在小格裡——掛進去的程式自己也開 `state.json` 窗的話兩個 loop 寫同一份檔（N-28 開頭 ②），得把裡面那層的窗改名或不開；② 少一層行程，SIGTERM 直接打到那支程式。`execs` 與 `loops` 共用名字空間（同一個名字兩邊都寫＝`CfgBad`）。

| 檔 | 做什麼 |
|---|---|
| `_entry` | `exec aos-daemon "$@" daemon.json`（後面的參數原樣給 daemon，例 `--max 50`） |
| `daemon.json` | 上面那份：`max` 10、`interval_ms` 200（約 2 秒收工）；信箱模式（`loops_mailbox`，下面「半路加一個」用 aos-daemon-ctl 投信）；`loops` 的 `tick_loop`（①）、`execs` 的 `tick_exec`（②）都指 `../tick`（相對路徑從 daemon 的 cwd＝`demo/daemon-3/` 算） |

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

結束碼 0。`.stack/loops_state.json`（pid、時間每次不同）：

```json
{"kind": "state", "ctl_seq": null, "ctl_warning": null, "letter_warning": null,
 "loops": {"tick_loop": {"pid": 135521, "started_at_ticks": 778245, "phase": "done", "code": 0, "signal": null}},
 "execs": {"tick_exec": {"pid": 135522, "started_at_ticks": 778245, "phase": "done", "code": 0, "signal": null}},
 "pid": 135520, "started_at_ticks": 778245, "boot_id": "…", "recorded_at": "2026-10-30T02:03:32.502+00:00"}
```

`find .stack -type f | sort`：

```
.stack/loops_state.json
.stack/state.json
.stack/tick_exec/stderr.txt
.stack/tick_exec/tick.txt
.stack/tick_loop/loop.json
.stack/tick_loop/state.json
.stack/tick_loop/stderr.txt
.stack/tick_loop/tick.txt
```

兩格的 `tick.txt` 都是 `5`、`stderr.txt` 都是空的；`tick_loop/loop.json`＝`{"exec": "<絕對路徑>/demo/daemon-3/../tick", "max": 1, "ctl": "ctl.json", "state": "state.json", "_entry": ["aos-loop", {"$env": "AOS_CF"}]}`（daemon 補的 ctl／state 與 `_entry`）。`tick_exec/` 只有 stderr 與程式自己的時鐘檔。

## 半路加一個（aos-daemon-ctl）

`aos-exec XXX`＝掛到 Linux 的 proc 管理；`aos-daemon-ctl add XXX`＝掛到 daemon 上（[bin/README](../../bin/README.md)）。它往 daemon 的信箱投一封 `loops_added`／`execs_added` 的信（N-54 的手把；信箱模式，所以這份 daemon.json 寫了 `loops_mailbox`）。哪個 daemon＝`--daemon` ＞ `$AOS_DAEMON`（daemon 的 `$AOS_STACK`）。XXX 有 `loop.json`＝掛成 loop 子項（子 loop 直接跑它的 loop.json）、沒有＝掛成 `execs`；`--kind max1` 強制包成 `{"exec": XXX, "max": 1}`。

```sh
aos-exec $R/demo/daemon-3 --max 50 &       # 約 10 秒
export AOS_DAEMON=$ws/.stack
until [ -d $AOS_DAEMON/loops_mailbox/new ]; do sleep 0.1; done
aos-daemon-ctl add $R/demo/tick                               # tick 有 loop.json＝loop 型、名字 tick；印信號
aos-daemon-ctl add --name tick_max1 --kind max1 $R/demo/tick  # ① 的寫法
sleep 1; aos-daemon-ctl ls
aos-daemon-ctl rm tick_max1; sleep 1; aos-daemon-ctl ls
wait; echo "結束碼 $?"
```

第一次 `ls`（名字、種類、phase、pid、code；pid 每次不同）：

```
tick_loop	loop	done	135552	0
tick	loop	done	135580	0
tick_max1	loop	done	135581	0
tick_exec	exec	done	135553	0
```

`rm tick_max1` 之後那一列不見了；結束碼 0。

`run.sh` 的 daemon-3 段跑上面「怎麼跑」那次、印 stack 樹；自動測：`impls/aos-daemon/tests/test_demo.py`（`run_daemon3`）。
