這份教你怎麼讓一隻 eca-claude 暫停、繼續、停下、再起（試驗 13，11-18 晚在家機用 haiku 實跑過）。
← [目錄](README.md)

使用者原話：「用 aos-loop 控制 eca-claude 的停止與繼續」

## 結論

- **`aos-loop` 本身沒有子指令**，不能對它打 `aos-loop pause`。它是 agent 的外殼（`loop.json`），靠兩樣東西控制：**ctl 窗**（stack 裡的 `ctl.json`）和**訊號**。日常用 `aos-agent ctl pause／resume／stop／start／sleep／wake`，其中 pause、resume、stop 就是替你寫 `ctl.json`。
- 三對指令，各自只還原自己那一對：

| 想做的 | 指令 | 表上變成 | 還原 |
|---|---|---|---|
| 原地暫停（行程還活著） | `ctl pause` | `paused` | `ctl resume` |
| 這輪做完就停 | `ctl stop` | `stopped` | `ctl start` |
| 馬上停（SIGTERM） | `ctl sleep` | `sleeping` | `ctl wake` |

- **pause、stop 都不打斷正在想的那一輪**：等這輪答完才生效。`pause` 等不到會先印 warning，`stop` 會一直等到停好。要馬上停用 `sleep`。
- 停著時 `say` 照寄，信留在 `queue/new/`，恢復之後照答（見 [14](14-停著時say.md)）。

下面都在樹根 `~/aos-home` 打，視窗都先 `source env.sh`，樹照 [README 的「共同準備」](README.md#共同準備)起好、ann 已掛上、模型 haiku。`-d .stack` 可省（見 [02](02-預設stack與站在agent夾裡.md)），這裡照寫。

## 一步一步

**1. 看控制檔在哪**

```sh
cat .stack/procs/ann/ctl.json; cat .stack/procs/ann/state.json
```

會看到：`ctl.json` 一開始**不存在**（有人下過指令才有）。`state.json` 是 loop 自己寫的：`{"phase": "running", "paused": false, "pid": …, "interval_ms": 300, …}`。`loop.json` 裡 `"ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"` 就是這三個窗。

**2. 暫停**

```sh
aos-agent -d .stack ctl pause ann
```

會看到：`paused ann; aos-agent ctl resume --target ann to continue`。

```sh
cat .stack/procs/ann/ctl.json; cat .stack/procs/ann/state.json; cat .stack/procs/ann/state_flux.json; aos-agent -d .stack ctl ls -l
```

會看到：

```
{"cmd": "pause", "seq": 1}
{"phase": "paused", "max": null, "interval_ms": 300, "paused": true, "pid": 427844, …}
{"responded_at": "2026-11-18T13:00:23.286+00:00", "ctl_seq": 1, "ctl_warning": null}
ann	paused	/home/…/home	0	-	0	0	-	-
```

`ctl.json` 是你寫的命令（`seq` 每下一次加一），`state_flux.json` 是 loop 的回應（`ctl_seq` 對得上就是它收到了）。**pause 時行程還在**，daemon 表上 phase 顯示 `paused`。

**3. 暫停時 say**

```sh
aos-agent -d .stack --target ann say "reply with the single word: paused-test"
aos-agent -d .stack --target ann listen --timeout-s 8
```

會看到信件名稱，加一行 warning：`ann is paused and will not answer until resumed: aos-agent ctl resume --target ann`；`listen` 等 8 秒報 `AnswerMissing waited 8 s; … is not answered yet (the letter is in queue/new/)`。

**4. 繼續**

```sh
aos-agent -d .stack ctl resume ann; aos-agent -d .stack --target ann listen --timeout-s 60
```

會看到 `resumed ann`，然後 `paused-test`：停著時寄的信現在被答了。

**5. 不用指令，自己寫 ctl.json（原理）**

```sh
echo '{"cmd":"pause","seq":3}' > .stack/procs/ann/ctl.json; sleep 1; cat .stack/procs/ann/state_flux.json
echo '{"cmd":"resume","seq":3}' > .stack/procs/ann/ctl.json; sleep 1; cat .stack/procs/ann/state.json | cut -c1-60
echo '{"cmd":"foo","seq":4}' > .stack/procs/ann/ctl.json; sleep 1; cat .stack/procs/ann/state_flux.json
```

會看到：第一句之後 `state.json` 變 `paused`；第二句同一個 `seq` 也生效（回到 `running`；我沒再查 loop 到底認不認同號）；第三句寫不認得的命令，`state_flux.json` 變 `"ctl_warning": "ctl rejected: cmd must be \"pause\", \"resume\" or \"stop\""`，`ctl_seq` 停在上一個。**cmd 只有這三個**。平常用 `aos-agent ctl`，它替你加 seq、等 loop 回應；手寫要自己記得 `seq` 往上加。

**6. 一輪做到一半時 pause**

```sh
aos-agent -d .stack --target ann say "run the bash command 'sleep 20' once, then reply with the single word: slept"
sleep 6; aos-agent -d .stack ctl pause ann
```

會看到 5 秒後一行 warning：`ann has not applied pause (seq 7) within 5 s (it reads its ctl between steps; a long step delays it); a stop or sleep sent before it applies overwrites or drops it`，接著 `paused ann …`。這時 `ctl ls -l` 還是 `running`，那輪做完（約 20 秒、`listen` 拿到 `slept`）才變 `paused`。**命令寫進去了，等這輪結束才套用**。

**7. 停（這輪做完就停）、再起**

```sh
aos-agent -d .stack ctl stop ann; cat .stack/procs/ann/ctl.json; aos-agent -d .stack ctl ls -l
```

會看到 `stopped, stack kept (…); say still queues letters meanwhile, aos-agent ctl start --target ann to carry on`；`ctl.json` 是 `{"cmd": "stop", "seq": 6}`；表上 `stopped`；`state.json` 的 `phase` 是 `stopped`、`code` 是 0。

```sh
aos-agent -d .stack ctl start ann
```

會看到 `started (same stack); 0 queued letter(s) will be answered next`。**如果停之前是 paused，起來還是 paused**：`… it was paused when it went down, so it comes back paused: aos-agent ctl resume --target ann`，要再 `resume` 一次。

**8. 一輪做到一半時 stop**

```sh
L=$(aos-agent -d .stack --target ann say "run the bash command 'sleep 15' once, then reply with the single word: done15")
sleep 4; aos-agent -d .stack ctl stop ann
```

會看到：`stop` 這句**卡了約 14 秒**才回（等那輪做完），之後表上是 `stopped`。`ctl start` 後 `listen --letter $L` 拿到 `done15`：那輪沒被切掉。

**9. 馬上停、再叫醒**

```sh
aos-agent -d .stack ctl sleep ann
aos-agent -d .stack --target ann say "reply with the single word: woke"
aos-agent -d .stack ctl wake ann; aos-agent -d .stack --target ann listen --timeout-s 60
```

會看到：`asleep, stack kept (…); … wake it: …`，表上 `sleeping`；`say` 的 warning 說 `it is asleep on the daemon (ann is sleeping); wake it: aos-agent ctl wake --target ann …`；`wake` 說 `awake (same stack); 1 queued letter(s) will be answered next`，然後拿到 `woke`。`sleep` 是對行程發 SIGTERM，所以不等那輪；daemon 整台關掉時所有 proc 也是用這種方式睡下，daemon 再起來會自己醒（見 [06](06-不用aos-tree-start起daemon.md)）。我沒在一輪做到一半時下 `sleep`，那輪被切掉的細節未實測。

## 沒實測的

- 直接手動跑 `aos-loop`（不經 daemon）加 `--ctl` 的用法；上面都是 daemon 起的 loop。
- 直接對 loop 行程發訊號（`kill -TERM`）；`sleep` 就是 daemon 幫你發。
- `--max`、`--interval-ms` 等旗標（`aos-loop --help` 有列，這份沒動）。

## 發現的問題

1. `pause` 等不到套用只印 warning、退 0，看不到「真的暫停了沒」，要再看 `ctl ls` 或 `state.json`。
