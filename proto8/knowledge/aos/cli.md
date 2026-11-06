# Commands for humans and external agents

The `aos-agent` command: one command, every subcommand acts on one agent. Use this when you are a coding agent or a person at a shell, not an agent inside aos.

Which daemon: `--daemon <stack>` > `$AOS_DAEMON` > `./.stack` in the current folder. Which agent: `--target <name>` > `$AOS_AGENT`.

Start and manage (`ctl`):

- `aos-agent ctl add --name bob ../agents/bob`: start an agent from a definition folder. Options `--ws DIR`, `--limits '{"mem_mb": 512}'`.
- `aos-agent ctl ls`: the daemon table (name, phase, ws, queue, reason).
- `aos-agent ctl state --target bob`: one agent in detail (phase, ws, definition, stack, queue, last answer, `reason`, `tools overlay`, `limits`).
- `aos-agent ctl stop|start --target bob`: stop keeps the stack; start brings a `stopped` one back.
- `aos-agent ctl sleep|wake --target bob`: sleep now; wake a `sleeping` one. Using the wrong pair gives `PhaseBad` with the right command in the message.
- `aos-agent ctl pause|resume --target bob`: pause between steps.
- `aos-agent ctl rm bob`: remove it and delete its stack.
- `aos-agent ctl who`: which agent owns `$AOS_STACK` (for tools asking "who called me").
- `aos-agent ctl where --target bob`: print its stack (`--ws` for its workspace).

Talk:

- `aos-agent say --target bob "hello"` then `aos-agent listen --target bob --timeout-s 60`: send a letter, wait for the answer.
- `aos-agent chat --target bob`: a line-by-line conversation; Ctrl-C to leave.

Per-agent settings (overlays; the definition is never changed):

- `aos-agent tools --target bob ls|add <name> <path>|rm <name>|reset`
- `aos-agent llm --target bob show|set endpoint=smart-high|reset`

Brain service: `aos-llm ls` lists endpoint packs; `echo '<letter>' | aos-llm ask` asks once. Needs `AOS_LLM_KERNEL`.

Errors: one line `aos-agent: error: Code reason` on stderr, exit 1; `warning:` lines are not errors. `TargetMissing` = no `--target` and no `$AOS_AGENT`; `InstanceMissing` = no such name in the table; `DaemonMissing` = no daemon found, or the daemon did not reply within 30 s (busy, paused or down; the letter stays in its mailbox and may still be applied later). Do not retry in a row; check `aos-daemon-ctl ping`, try again later.

11-06 note（11-06 註）: To call a registered tool from a shell, use `printf '%s' '{"path":"a.txt"}' | aos-tools --file tools.json call read`. Folder, JSON and executable tools all receive the JSON object unchanged on stdin through `aos-exec`. `aos-tools call` alone assigns the tool's scratch stack: with a parent `$AOS_STACK`, the child gets `<parent>/tools/<registered-name>/`; without one, `aos-exec` supplies its default. Callers pass their own stack. See [J3 implementation](../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j3-aos-tools-收口).

11-06 note（11-06 註）: Register hub locations with `aos-tools --file tools.json add --name read --env-file hubs.env --envs AOS_MEMORY=/data/memory ../lib/base/read` (or the same options on `aos-agent tools --target bob add`). Repeat `--envs K=V` as needed. At registration, `--envs` overrides the file; the resulting values are saved in the registry and override inherited environment at call time. Editing the file later has no effect until registration is replaced with `--override`. Registry values cannot override the scratch `AOS_STACK`. Missing hubs declared by the tool produce a warning and registration still succeeds. Tool input stays in stdin JSON. See [J3 implementation](../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j3-aos-tools-收口).

11-06 note（11-06 註）: Lib tools also accept schema-derived flags such as `aos-exec lib/base/read --path a.txt --max-lines 1`. Flags override stdin keys; `--a.b V` changes only that leaf; extra stdin keys are ignored, unknown flags give `FlagUnknown`. A terminal stdin is treated as `{}` without reading. Parameters, defaults and declared error codes in `--help` come from `_tooldef.json`; prose explains results. Human commands use `aos_flags`, which shares the tokenizer in `lib/tool_io.py`. See [J1 implementation](../../thinking/2026-11/05/json-argv/08-J1實作結果.md), [J2 implementation](../../thinking/2026-11/05/json-argv/09-J2實作結果.md), and [J5 implementation](../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j5-aos_flags-去重sigpipe).
