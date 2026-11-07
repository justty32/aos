# aos-daemon-ctl 永遠直寄、不看 AOS_KERNEL 的裁定與實作結果（11-07 早家機）

← [入口](README.md)｜上一份 [07-C5留格與AOS_KERNEL提醒實作結果](07-C5留格與AOS_KERNEL提醒實作結果.md)｜前因 [06 K-3](06-判官排隊第二步實作結果.md)

## 使用者原文與裁定（11-07 早，逐字）

先說：

> 話說AOS_KERNEL= aos-agent ctl wake --target 名字  這個寫法好醜

選項框三個選項裡選了「**aos-daemon-ctl 永遠直寄**」，選項說明原文：

> 分工變清楚：aos-agent＝經作業系統（判官），aos-daemon-ctl＝人直接敲板子，不管 AOS_KERNEL。叫醒判官就寫 `aos-daemon-ctl wake 名字`。對應「板子／作業系統」比喻，也對應 C-83「人是最後保底」。代價：aos-daemon-ctl 現在會走判官，改完就不走了，人要判官管控就用 aos-agent；助說明、知識庫要改。

同時補一句：

> 判官睡着，這是使用者在設計系統時要承擔與管理的風險。

→ 只做「aos-daemon-ctl 永遠直寄」；**不加**任何自動叫醒判官、判官掛了自動繞過之類的機制。文件講到判官睡著時寫「這是設計系統的人要管的風險，手動用 `aos-daemon-ctl wake` 叫醒」。

## 一句話結論（白話）

`aos-daemon-ctl` 現在是「人直接敲板子」：不管有沒有設 `AOS_KERNEL`，信一律寄進 `--daemon`／`$AOS_DAEMON`／`./.stack` 那台 daemon 自己的 ctl 信箱，也不再印 `routing via AOS_KERNEL` 提醒。要判官管控的，用 `aos-agent ctl`（照舊經 `AOS_KERNEL`）。判官自己睡著時就 `aos-daemon-ctl wake 判官名`。

## 做了什麼

| 項 | 改了什麼 | 檔 |
|---|---|---|
| 直寄 | `deliver`（add／rm／stop／start／sleep／wake）與 `ping` 改呼叫共用套件的 `direct=True`；刪 `routing_warning`；逾時提醒、ping 錯誤訊息拿掉判官字樣（「判官拒絕 ping」那條分支一併刪：直寄時沒有判官會拒） | `cmd/aos-daemon-ctl/bin/aos-daemon-ctl` |
| `--queue-wait-s` | **拿掉**（add／start／wake）；給了＝`FlagUnknown` | 同上 |
| 共用套件 | 行為不動：`mailbox_of`／`send`／`ping` 沒給 `direct` 照舊看 `AOS_KERNEL`（aos-agent 走這條）；只改 `mailbox_of` 的說明句 | `py/daemon_ctl/post.py` |
| help | 頂層改成 "Letters always go straight to this daemon's ctl mailbox; AOS_KERNEL is not read. To go through the judge (AOS_KERNEL), use aos-agent ctl instead."；子命令拿掉 `--queue-wait-s` 與 "does not route through AOS_KERNEL"；ping 說明改 | 同上 |
| 文件 | cmd/docs/03（掛信寄哪改寫、刪排隊期限與路由不認身份兩條、回信／逾時／ping 句）、aos-daemon-ctl README、kernel/docs/02（有設、約定那級、--reply-to、0 號睡著）、aos-agent README／docs 01／02（叫醒判官改 `aos-daemon-ctl wake`）、knowledge `aos/cli/daemon.md`、judge `_entry` 註解一句 | — |
| 條文 | N-63 實例 `AOS_KERNEL` 那條加 11-07 註／改讀、原句全留；CONCEPTS／CONVENTION 沒有講 aos-daemon-ctl 走判官的句子 | `docs/NORMS/10-…/07-…/01-N-63-…` |
| wf | WAIT_USER「對判官本身下指令改寫法」那條改新寫法；os-impl 06 兩處加 11-07 註 | — |

## 代定（可翻案）

1. **`--queue-wait-s` 整個拿掉**，不保留、不留舊名提示：它只是寫 body 的 `queue_wait_ms` 給判官看，直寄 daemon 時 daemon 忽略此欄，留著＝沒作用的旗標（使用者 11-05「proto8 沒有舊版」）。要排隊期限用 `aos-agent ctl add/start/wake --timeout-s S --on-queued fail`。
2. **不提醒「設了 AOS_KERNEL 但這支不看」**：裁定原文就是「不管 AOS_KERNEL」，再印一行等於又讓這支認它；help 第一屏寫清楚。
3. **共用套件的預設不翻**：`direct` 預設 False＝看 `AOS_KERNEL`，因為現在唯一的寄信呼叫者 aos-agent 要的就是這條；aos-daemon-ctl 明帶 `direct=True`。
4. **歷史 thinking 不改**：11-05～11-06 的盤點、規劃、實測記錄裡寫「aos-daemon-ctl 經判官」的照當時事實留著；只改活文件、條文加註、06 加註。

## 實測（11-07 早家機，`/tmp/dc-direct-1107`，假腦＝範本 agent-fsm 不送信就不問腦）

模式 2：一台 daemon、判官（`kernel/procs-kernel` 複本，`allowed: [bob, bob2]`、`max_running: 2`）掛成 `judge`、`AOS_KERNEL=$AOS_DAEMON/procs/judge/requests`：

| 步 | 結果 |
|---|---|
| `aos-agent ctl add bob` | stderr `aos-agent: warning: routing via AOS_KERNEL=…/procs/judge/requests`、上表 running（經判官） |
| `aos-daemon-ctl sleep judge` | 沒有 routing 提醒，表上 `judge sleeping`（直寄，判官本身成功睡） |
| 判官睡著時 `aos-agent ctl add --timeout-s 3 bob2` | `DaemonMissing … letter withdrawn …`（照舊經判官、沒人轉） |
| `aos-daemon-ctl ping` | `replied in 52 ms`（直寄 daemon，不受判官睡著影響） |
| `aos-daemon-ctl wake judge` | 表上 `judge running`（判官本身成功醒） |
| `aos-agent ctl add --timeout-s 10 bob2` | `AddRejected … SlotMissing max_running is 2, 2 running now …`（判官醒了照判） |
| `aos-daemon-ctl wake --queue-wait-s 1 judge` | `FlagUnknown unknown flag --queue-wait-s (see aos-daemon-ctl wake --help)` |
| `aos-daemon-ctl add <clock 的 loop.json>`（判官已滿 2） | 上表 running、表上 3 列——直寄繞過判官的 `max_running` |

收尾：只對自己起的 daemon pid 送 SIGINT，`ps` 沒有殘留。

改後 `aos-daemon-ctl --help`（全文）：

```text
aos-daemon-ctl - attach procs to an aos-daemon and start / stop / sleep / wake / pause them

usage: aos-daemon-ctl [--daemon D] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-daemon-ctl SUBCOMMAND --help

subcommands:
  add [FLAGS] XXX [-- ARGS...]   attach (register + start); prints the letter name
  rm NAME        detach (stop, then remove; stack kept, so it does not ask)
  stop NAME      stop after this run (row stays as stopped)
  start NAME     start a stopped one again on the same stack
  sleep NAME     SIGTERM now (row stays as sleeping; wakes when the daemon restarts)
  wake NAME      start a sleeping one again on the same stack
  pause NAME     write {"cmd": "pause", "seq": N} to its ctl window; prints N
  resume NAME    the same with "resume"
  ls [-j]        the table: NAME  PHASE  PID  CODE  WS  REASON; last line = the supervisor's view
  where --stack NAME   print its stack (one absolute path)
  ping [--timeout-s S]   wait for the daemon's ping reply; prints "replied in N ms"

Each subcommand drops one letter into the daemon's ctl mailbox (procs_added, procs_removed,
procs_stopped, ...) or writes the proc's own ctl window (pause / resume). A letter only
asks; the daemon applies it on its next round. See the result with ls.
Letters always go straight to this daemon's ctl mailbox; AOS_KERNEL is not read.
To go through the judge (AOS_KERNEL), use aos-agent ctl instead.
add / rm / stop / start / sleep / wake also take --reply-to BOX (send only, do not wait).

flags:
  -d, --daemon D   the daemon's stack folder (default: $AOS_DAEMON, else ./.stack)
  -h, --help       show this help
  short names: -n --name, -w --ws, -s --stack, -j --json

exit codes: 0 sent / printed; 1 error ("aos-daemon-ctl: error: CODE reason" on stderr).
more: proto8/cmd/docs/03-aos-daemon-ctl.md
```

改後 `aos-daemon-ctl wake --help`：

```text
aos-daemon-ctl wake - start a sleeping proc again on the same stack

usage: aos-daemon-ctl [--daemon D] wake [--reply-to BOX] [--timeout-s S] NAME

Asks a sleeping proc to start again on its recorded stack. A stopped proc needs start.
Prints the letter name; without --reply-to, waits up to --timeout-s seconds for it to leave new/.

flags:
      --timeout-s S    positive claim timeout (default: 3); excludes --reply-to
      --reply-to BOX   send only; the reply goes to BOX
  -h, --help           show this help

exit codes: 0 sent; 1 error (including PhaseBad).
```
