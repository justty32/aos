← [入口](README.md)｜涵蓋：照慣例後 aos-daemon-ctl 的 `--help` 全文（頂層、`add`、`ls`）；單檔不拆、只拆 help｜上一份 [01-樣本-aos-agent-續](01-樣本-aos-agent-續.md)｜下一份 [02-盤點](02-盤點.md)

# 樣本：aos-daemon-ctl

現況：每個子命令的 `--help` 都印同一份 85 行 9.7 KB；錯誤行把全部子命令的 usage（200 多字）塞在原因後面。S6（no-pid P3）已把本體搬進 `py/daemon_ctl.py`，`bin/aos-daemon-ctl` 剩 372 行薄殼——**不拆套件**（沒超過多少、也沒有群組），只把 HELP 拆成「頂層一份＋每個子命令一份」的 dict，錯誤行改接那個子命令的一行。

## `aos-daemon-ctl --help`（頂層，一屏）

```
aos-daemon-ctl - attach procs to an aos-daemon and start / stop / sleep / wake / pause them

usage: aos-daemon-ctl [--daemon D] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-daemon-ctl SUBCOMMAND --help

Each subcommand drops one letter into the daemon's ctl mailbox (procs_added, procs_removed,
procs_stopped, ...) or writes the proc's own ctl window (pause / resume). A letter only
asks; the daemon applies it on its next round. See the result with ls.

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
  where NAME     print its stack (one absolute path)
  ping [--timeout-s S]   wait for the daemon's ping reply; prints "replied in N ms"

flags:
  -d, --daemon D   the daemon's stack folder (default: $AOS_DAEMON, else ./.stack)
  -h, --help       show this help
  short names: -n --name, -w --ws, -s --stack, -j --json

letters go to $AOS_KERNEL (the judge) when it is set; a warning line says so.
add / rm / stop / start / sleep / wake also take --reply-to BOX (send only, do not wait).
exit codes: 0 sent / printed; 1 error ("aos-daemon-ctl: error: CODE reason" on stderr).
more: proto8/cmd/docs/03-aos-daemon-ctl.md
```
（`where NAME` 是 S9 候選：現況 `where --stack NAME`，對象寫成旗標、而且必填；見 [05 衝突 8](05-邊緣與衝突.md)。沒裁就印現況。）

## `aos-daemon-ctl add --help`

```
aos-daemon-ctl add - attach one proc (register + start)

usage: aos-daemon-ctl [--daemon D] add [--reply-to BOX] [--name N] [--ws WS] [--stack S]
                      [--def DEF] [--limits JSON] XXX [-- ARGS...]

XXX is followed the way aos-exec follows it: ending at a loop config = loop type (no ARGS
allowed), anything else = exec type (runs once; ARGS after -- are appended). Prints the
letter name, then waits up to 3 seconds for the letter to leave new/ (still there = a
warning line, exit 0; it is applied when taken).

flags:
  --reply-to BOX   send only; the reply ({"applied": true|false, ...}) goes to BOX
  -n, --name N     its name on the table (default: the folder name of XXX)
  -w, --ws WS      its workspace (default: the daemon's)
  -s, --stack S    its stack (default: <D>/procs/<name>/)
  --def DEF        the definition folder recorded on the table (default: XXX)
  --limits JSON    resource limits, the aos-sandbox keys ('{}' = none)
  -h, --help       show this help

exit codes: 0 sent; 1 error (ArgumentsBad, DaemonMissing, MailboxMissing, PathMissing,
  EntryBad, SendFailed...).
```

## `aos-daemon-ctl ls --help`

```
aos-daemon-ctl ls - list the procs on the daemon table

usage: aos-daemon-ctl [--daemon D] ls [-j]

One line per proc: NAME TAB PHASE TAB PID TAB CODE TAB WS TAB REASON (none = -); paths are
absolute. The last line starts with "# " and says what the supervisor thinks of this daemon
("# root daemon (no supervisor)" for a root). Only reads files; it does not ping.

flags:
  -j, --json   one line {"procs": table, "daemon": UP or null, "supervisor": {...} or null}
  -h, --help   show this help

exit codes: 0 (an empty table prints only the last line); 1 error (DaemonMissing,
  StateMissing, StateBad).
```

## 錯誤行照慣例後（對照現況）

```
現況  aos-daemon-ctl: error: ArgumentsBad missing subcommand (usage: aos-daemon-ctl [--daemon D] add [--reply-to BOX] [--name N] [--ws WS] [--stack S] [--def DEF] [--limits JSON] XXX [-- ARGS...] | rm|stop|start|sleep|wake [--reply-to BOX] NAME | pause NAME | resume NAME | ls [--json] | where --stack NAME | ping [--timeout-s S])
改後  aos-daemon-ctl: error: ArgumentsBad missing subcommand (add, rm, stop, start, sleep, wake, pause, resume, ls, where, ping; see aos-daemon-ctl --help)
改後  aos-daemon-ctl: error: ArgumentsBad rm needs one NAME (usage: aos-daemon-ctl [--daemon D] rm [--reply-to BOX] NAME)
改後  aos-daemon-ctl: error: FlagUnknown unknown flag --bogus                       ← 子命令前，不附 usage（stdio-unify D9）
```

## 檔案結構（不拆套件）

```
cmd/aos-daemon-ctl/
├─ bin/aos-daemon-ctl    HELP（頂層）、HELPS = {"add": "...", "rm": "...", ...}；cmd_* 各一函式（現況）；
│                        錯誤的 usage 取 HELPS[子命令] 的 usage 行；檔頭中文長註解搬去 cmd/docs/03、04
└─ README.md             指到 cmd/docs/03、04（現況）
```

S6 之後 `py/daemon_ctl.py`（569 行）是模組、不是指令，不套本慣例；它超 300 行歸 S8 的拆檔清單另算。
