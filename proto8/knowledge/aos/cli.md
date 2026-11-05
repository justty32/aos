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

Errors: one line `aos-agent: error: Code reason` on stderr, exit 1; `warning:` lines are not errors. `TargetMissing` = no `--target` and no `$AOS_AGENT`; `InstanceMissing` = no such name in the table; `DaemonMissing` = no daemon found.
