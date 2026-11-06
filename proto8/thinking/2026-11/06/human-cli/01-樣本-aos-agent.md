← [入口](README.md)｜涵蓋：照慣例後 aos-agent 的 `--help` 全文（頂層、`ctl`、`ctl add`、`say`、`listen`）與 `cmd/aos-agent/` 子資料夾結構示意——使用者「實作的時候我要看一眼」的那份｜下一份 [01-樣本-aos-daemon-ctl](01-樣本-aos-daemon-ctl.md)

# 樣本：aos-agent

規則見 [03](03-慣例草案.md)。數字（秒數、代號）照現況；只改形狀。現況：`aos-agent --help` 與每個子命令的 `--help` 都印同一份 64 行 7.7 KB，第二層動作（`tools ls --help`）印不出來。

## `aos-agent --help`（頂層，一屏）

```
aos-agent - talk to and manage one agent hosted on an aos-daemon

usage: aos-agent [--daemon D] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-agent SUBCOMMAND --help        that subcommand's own help

subcommands:
  ctl      attach, list and manage agents (ctl --help lists its actions)
  say      put one message in its queue; prints the letter name
  listen   print its answer (wait for it, or show the last N)
  chat     one line per message, waits for each answer; Ctrl-C exits
  open     attach to its screen (--detach: open only)
  close    close its screen
  watch    follow its screen until one answer ends
  tools    its toolbox: ls, get, add, rm, reset
  llm      its brain settings: show, set, reset

flags:
  --daemon D   the daemon's stack folder (default: $AOS_DAEMON, else ./.stack)
  --help       show this help

target: every subcommand except ctl add / rm / ls / who acts on --target NAME
  (default: $AOS_AGENT); neither = TargetMissing.
output: results on stdout only (one line per item, TAB-separated; --json where listed);
  reminders on stderr as "aos-agent: warning: ...".
exit codes: 0 ok; 1 error ("aos-agent: error: CODE reason" on stderr); 130 on Ctrl-C.
more: proto8/cmd/aos-agent/README.md (rules, codes, examples)
```

## `aos-agent ctl --help`（群組）

```
aos-agent ctl - attach, list and manage agents on the daemon table

usage: aos-agent [--daemon D] ctl ACTION [FLAGS...] [ARGS...]
       aos-agent ctl ACTION --help

actions:
  add [--name N] [--ws WS] [--stack S] [--limits JSON] XXX
                          attach one; waits until it is on the table, prints its stack
  rm NAME                 detach it and delete its stack (NAME must be spelled out)
  ls [--json]             every proc on the table: NAME  STATE  WORKSPACE  QUEUED  REASON
  state [--target NAME]   a few lines about this one (status = the same)
  where [--ws] [--target NAME]
                          print its stack (default) or its workspace (--ws)
  who [--json] [STACK]    which listed agent owns STACK (default: $AOS_STACK)
  start | stop | sleep | wake | pause | resume [--target NAME]
                          stop = after this round, start brings it back;
                          sleep = now, wake (or a daemon restart) brings it back;
                          pause / resume = the loop's own ctl window

flags:
  --help   show this help

exit codes: 0 ok (asking for the state it is already in prints "already ..." and exits 0);
  1 error, e.g. PhaseBad (wrong state for start/stop/sleep/wake), InstanceMissing, AddRejected.
more: proto8/cmd/aos-agent/README.md
```
（`who [STACK]` 是 S9 候選：現況 `who --stack S`，同一個 `--stack` 在 `where` 是開關、在 `who` 是路徑，兩義；見 [05 衝突 8](05-邊緣與衝突.md)。沒裁就照現況印 `who [--stack S] [--json]`。）

## `aos-agent ctl add --help`（二層動作）

```
aos-agent ctl add - attach one agent to the daemon

usage: aos-agent [--daemon D] ctl add [--name N] [--ws WS] [--stack S] [--limits JSON] XXX

XXX is the agent folder; it must declare aos-agent in interfaces.json. The letter goes
through $AOS_KERNEL when that is set (a warning line says so). Waits until the agent is on
the table, then prints its stack; the daemon refusing it = AddRejected.

flags:
  --name N        its name on the table (default: the folder name of XXX)
  --ws WS         its workspace (default: the current directory)
  --stack S       its stack (default: <daemon stack>/procs/<name>/)
  --limits JSON   resource limits, the aos-sandbox keys ('{}' = none)
  --help          show this help

exit codes: 0 attached; 1 error (InterfaceMissing, InstanceExists, AddRejected, DaemonMissing...).
```

## `aos-agent say --help`

```
aos-agent say - put one message in the agent's queue

usage: aos-agent [--daemon D] say [--target NAME] [WORDS...]
       ... | aos-agent [--daemon D] say [--target NAME]

WORDS are joined with single spaces into one message. No WORDS (or "-") = the whole of
stdin is the message (one trailing newline dropped); stdin being a terminal = ArgumentsBad.
stdout prints the letter name. A paused or sleeping agent still queues it; a warning says so.

flags:
  --target NAME   which agent (default: $AOS_AGENT)
  --help          show this help

exit codes: 0 queued; 1 error (TargetMissing, InstanceMissing, PostFailed...).
```

## `aos-agent listen --help`

```
aos-agent listen - print the agent's answer

usage: aos-agent [--daemon D] listen [--target NAME] [--timeout-s SECS]
       aos-agent [--daemon D] listen [--target NAME] --last N [--follow]

Without --last: wait for the answer to the latest question and print only its text (so
> file and pipes work; notes go to stderr). --last N prints the last N exchanges as blocks:
a line "== #N", the question lines prefixed "> ", then the answer. --follow keeps printing
new ones; Ctrl-C leaves with exit 0.

flags:
  --target NAME      which agent (default: $AOS_AGENT)
  --timeout-s SECS   give up after SECS seconds (AnswerMissing)
  --last N           show the last N exchanges instead of waiting
  --follow           with --last: keep following
  --help             show this help

exit codes: 0 printed; 1 error (AnswerMissing, QuestionUnknown...); 130 Ctrl-C while waiting.
```

## `cmd/aos-agent/` 子資料夾結構（S8 拆套件照這個；方向題 1 推薦）

```
cmd/aos-agent/
├─ bin/aos-agent              薄入口：realpath 找 ../../../py 與 ../aos_agent，aos_flags.run(aos_agent.main)
├─ aos_agent/
│   ├─ __init__.py            PROG、HELP（頂層那份）、main()：解 --daemon → 查 SUBS → 交給子命令
│   ├─ common.py              找 daemon、找 target、讀表、等回信、錯誤翻譯（ProcMissing→InstanceMissing）
│   ├─ ctl/
│   │   ├─ __init__.py        群組 HELP（從各模組 HELP 第一行拼）、SUBS = {"add": add, "rm": rm, ...}
│   │   ├─ add.py  rm.py  ls.py  state.py  where.py  who.py
│   │   └─ phase.py           start / stop / sleep / wake / pause / resume（六個小動作同主題一檔）
│   ├─ say.py  listen.py  chat.py        chat import say、listen 的函式
│   ├─ screen.py              open / close / watch
│   ├─ tools.py               tools ls / get / add / rm / reset（第二層用同一張 SUBS 表的寫法）
│   └─ llm.py                 llm show / set / reset
├─ README.md  docs/           中文：規則、代號全表、例子（現在 --help 裡的長篇英文散文搬過來、翻中文）
└─ using-aos-agent.sh  stack.gitignore  stack.gitattributes
```

- **一個子命令一個地方**：模組頂端 `HELP = """aos-agent say - ...` 就是它的 `--help`；`cmd(argv)` 一個入口函式；錯誤行的 `(usage: …)` 取 HELP 的 usage 行。群組（`ctl/__init__.py`）的 actions 段由各模組 HELP 第一行自動拼，不手抄兩份。
- **派發是一張表**：`SUBS = {"ctl": ctl, "say": say, …}`，`main` 查表、沒有＝`CommandUnknown`；二層同形（`ctl.SUBS`、`tools.SUBS`）。不掃資料夾、不 `importlib` 猜名字（C-56 寫什麼就做什麼）。
- **純搬移在前、形狀在後**：S8 先拆套件、`--help` 輸出 diff 為空（arch-refactor 驗收照舊），同一人緊接第二個 commit 把 HELP 分層（驗收見 [04](04-落到S8S9.md)）。
- 行數：現況 1,267 行；拆完最大的檔預估 `common.py`（約 250 行）、`chat.py`＋`listen.py`（約 200 行）；沒有 >300 行。
