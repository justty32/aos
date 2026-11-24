← [教學入口](README.md)｜上一章 [05 掛上去跑](05-掛上去跑.md)（從 [02](02-架daemon.md) 直接跳來也行）｜下一章 [06 接著開發（一）](06-接著開發-1-改與工具.md)

# 05b 起 eca_main（一隻 Claude Code 當腦的 agent）

**結論**：抄 `eca-claude` 範本到 `agents/eca_main`，`aos-agent ctl add` 掛上板子，`say`／`listen` 就跟它說上話。它的腦是你機器上的 `claude` 指令本身，不經 llm kernel、不用寫 `agent.py`，所以做完第 02 章就能直接來（板子開著就好）。

eca 是「外部 coding agent」：把 Claude Code（或 codex、pi）這種現成的 coding agent 包成一隻 aos agent。它每收到一批信就叫一次 `claude -p`，回答接進自己的 `history.jsonl`；看檔、改檔、下指令用 Claude Code 自己的工具（Read、Write、Edit、Bash…），aos 另外經 MCP 給它 18 支 aos 工具（信箱、時鐘、json…，在 Claude Code 裡叫 `mcp__aos__…`）。`eca_main` 是這隻的名字＝資料夾名，你想叫別的也行，後面指令裡的 `eca_main` 跟著換。

## 要先有什麼

- 第 02 章的板子開著（視窗 A 的 `aos-exec root`）。第 03～05 章（llm kernel、ann）沒做沒關係。
- `claude` 指令在 PATH 上、登入過。在視窗 B 看一下：

```sh
command -v claude
claude --version
```

```
/home/you/.local/bin/claude
2.1.330 (Claude Code)
```

找不到＝還沒裝，照 Claude Code 自己的說明裝。沒登入過＝先打一次 `claude`，照畫面登入，再 `/exit`。這一章會真的叫 Claude，花的是你的額度（訂閱或 API 都行）。

## 抄範本、掛上去（視窗 B）

```sh
mkdir -p agents
cp -r $AOS_HOME/templates/agents/eca-claude agents/eca_main
cat agents/eca_main/llm.json
aos-agent -d .stack ctl add --auto-restart -w . agents/eca_main
aos-daemon-ctl -d .stack ls
```

你會看到（做過 03～05 的話，表上還有 `llm`、`ann`）：

```
{"model": "opus", "reasoning_effort": "high"}
~/code/aos-tut/.stack/procs/eca_main
_clock	running	3584360	-	-	-
_sweeper	running	3584361	-	-	-
eca_main	running	3586691	-	~/code/aos-tut	-
# daemon: running (pid 3584358)
# root daemon (no supervisor)
```

- 這夾直接就是定義（json 手寫好的），不用編譯。`llm.json` 的 `opus`＝叫 `claude --model opus`。
- `ctl add` 印的是 eca_main 的 stack（跑起來的樣子）在哪；`-w .`＝工作區是整個教學夾，`claude` 就在這裡開。
- **範本給它的 Write、Edit、Bash 不問就准**：它改得到工作區裡的任何東西，也碰得到 `.stack/`；Read、Glob、Grep 也不問就准，工作區外的檔一樣讀得到。要它去別的專案做事，把 `-w .` 換成那個專案夾（例 `-w ~/code/myproj`）。

## 說一句話

```sh
aos-agent -d .stack --target eca_main say "Reply with exactly one word: pong"
aos-agent -d .stack --target eca_main listen --timeout-s 180
```

```
000000000001.01795244906466185828.3587135.3307680
pong
```

`say` 印的是那封信的名字；`listen` 等到回答就印出來。真模型一輪要幾秒到一兩分鐘，`--timeout-s` 給寬一點；講中文也行。叫一支 aos 工具試試：

```sh
aos-agent -d .stack --target eca_main say "What time is it? Use the peek_now_time tool and reply with just its output."
aos-agent -d .stack --target eca_main listen --timeout-s 180
```

```
000000000002.01795244917607670616.3587994.3308795
2026-11-21T07:08:39Z
```

## 看全身

```sh
aos-agent -d .stack ctl state --target eca_main
```

```
who       eca_main (def ~/code/aos-tut/agents/eca_main, ws ~/code/aos-tut, stack ~/code/aos-tut/.stack/procs/eca_main)
state     running (daemon phase running); 0 queued; last answer "pong"
tools     18 tools (index_view, json_add, json_del, json_get, json_len, json_ls, …)
llm       model=opus reasoning_effort=high
system    484 bytes from definition; first line "You run as an aos agent: aos hands you the letters in your queue, and your conve…"
hooks     6 hooks (brain_notify on brain_failed, context_wrap on on_clock, mail_notify on on_clock, screen_linger_start on after_start, screen_linger_stop on after_stop, timer on on_clock)
history   2 messages, 255 bytes (assistant 1, user 1)
mailbox   0 letters waiting
subagents 0/4 subagents
resources limits none; whole agent uses memory 2.8 MiB, cpu 0.0 s, 1 processes
time      now 2026-11-21T15:08:33+0800; up 0h00m14s
```

- `hooks` 那六個是範本帶的：例如 `mail_notify` 每分鐘看信箱、有新信就提醒它；`context_wrap` 在對話用到 35% 時叫它收尾再壓縮。
- `system` 是給它的開場說明：裡面叫它要知道 aos 怎麼用時去讀 `$AOS_HOME/knowledge/`（知識庫）。所以之後有問題，直接 `say` 問它就行。

## 開畫面：看它做事、直接在裡面打字

```sh
aos-agent -d .stack --target eca_main open
```

畫面就是 Claude Code 平常的樣子（在 aos 自己開的 tmux 裡）。**第一次開會先問信不信任這個資料夾**（`Is this a project you created or one you trust?`），游標預設在 `No, exit`，要選 `Yes, I trust this folder`。按 Ctrl-] 跳出，畫面留著、它照跑；畫面裡打 `/exit` 才關畫面。畫面開著時 `say` 的信也會送進畫面裡。（**只實跑到信任提示那一步**，之後未實跑。）

## 換模型、停了再跑

```sh
aos-agent -d .stack llm --target eca_main set model=sonnet
aos-agent -d .stack llm --target eca_main reset
aos-agent -d .stack ctl stop eca_main
aos-agent -d .stack ctl start eca_main
```

```
aos-agent: warning: created ~/code/aos-tut/.stack/procs/eca_main/llm.json (only the changed keys, the rest follows the definition; llm rm KEY or llm reset undoes)
model=sonnet
reasoning_effort=high
aos-agent: warning: deleted ~/code/aos-tut/.stack/procs/eca_main/llm.json (the changed keys); back to the definition's ~/code/aos-tut/agents/eca_main/llm.json
model=opus
reasoning_effort=high
stopped, stack kept (~/code/aos-tut/.stack/procs/eca_main); say still queues letters meanwhile, aos-agent ctl start --target eca_main to carry on
started (same stack); 0 queued letter(s) will be answered next
```

- `llm set` 只改這一隻跑起來的那份，下一輪起生效；`reset` 回定義的 `opus`。要整份定義換，改 `agents/eca_main/llm.json`。
- 停、睡、拿掉的四種方式跟第 05 章那張表一樣；全部關掉照第 08 章，`aos-daemon-ctl -d .stack shutdown` 一句連 eca_main 一起睡下，再開板子它自己醒、對話接著。

更多（換 codex、擋它的 Bash、接外部 MCP、子 agent）在 [eca-claude 範本說明](../../templates/agents/eca-claude/README.md)，或直接問 eca_main。
