# Your own subagents: subagent

Tool `subagent` starts agents that are yours. Only agents you started with it are yours: you can talk to them, change their tools, brain, history, hooks and system text, stop and remove them. They count against your quota.

One op per call:

- start: `{"op": "add", "def": "defs/helper", "name": "kid", "ws": "kid"}` (`def` = a definition folder; no definition yet? first `agent_def` `{"op": "new", "template": "agent-fsm", "path": "defs/helper"}`; `ws` = its workspace, relative to yours, created if missing; default = your own)
- more add options (`stack`, `limits`, `envs`, `auto_restart` ...): `aos/agents/subagent.md#/subagent add: more options`
- list yours: `{"op": "ls"}` (one line per subagent: NAME STATE WORKSPACE QUEUED REASON, then `subagents N/MAX`; `"long": true` adds health columns QUEUE RESTARTS COOLDOWN LAST ERROR; `"json": true` = every field as JSON)
- ask and wait: `{"op": "ask", "name": "kid", "text": "what time is it?"}` (runs `aos-agent ask`: you get the answer to this message, even if others talk to the subagent at the same time; waits with no time limit by default; `timeout_s` sets one (0 = no limit), or `timeout_cycles` waits that many clock cycles instead)
- say now, read later: `{"op": "say", "name": "kid", "text": "hello"}` prints the letter name; then `{"op": "listen", "name": "kid", "letter": "<that name>"}` waits for the answer to it (like ask, the same `timeout_s` / `timeout_cycles`). Without `letter`, listen waits for the newest letter still in its queue, else the last one it took and has not answered, else gives the latest answer. `"last": 3` shows the last 3 without waiting (not with `letter`)
- its tools: `{"op": "tools", "name": "kid", "args": {"op": "add", "path": "tools/math"}}`
- its brain: `{"op": "llm", "name": "kid", "args": {"op": "set", "settings": {"model": "fake"}}}`
- its history, its hooks, its system text: `"op": "history"`, `"op": "hook"`, `"op": "system"`
- `{"op": "state", "name": "kid"}`; `stop`/`start`, `sleep`/`wake`, `pause`/`resume` the same way
- remove: `{"op": "rm", "name": "kid"}` (keeps its stack; `"purge": true` deletes it)

`say` is not a brake: the message waits in the subagent's queue, and an agent-fsm body takes it in only when it is back at idle, so a subagent in the middle of a run of tool calls does not see it yet. `pause` does not interrupt the step that is running; it only keeps the next step from starting. To stop a subagent at once, use `sleep`: the daemon ends its process, its stack is kept, and `wake` starts it again.

`args` is exactly what `self_tools`, `self_llm`, `self_history`, `self_hook` or `self_system` takes (see `aos/me.md`); the change lands on the subagent, not on you.

A wait longer than the MCP client's own tool timeout is still cut by that client; raise it there (Claude Code: environment MCP_TOOL_TIMEOUT, in ms) or use say + listen in shorter steps.

Quota and errors: `aos/agents/subagent.md#/subagent: quota and errors`.

# subagent: quota and errors

Quota: at most `max_subagents` subagents at once (default 4). It is set in `subagents.json` of your definition; a `subagents.json` in your own stack overrides it with only the keys you change, like `{"max_subagents": 2}`. The tool itself records who is yours (in your stack under `tools/subagent/`); do not edit that record.

- `SubagentSlotMissing`: your quota is full; nothing was started. `rm` a subagent you no longer need, or say the limit is reached. Do not retry in a loop.
- `AddRejected ... SlotMissing`: the daemon is full (its kernel counts every agent), not your quota. Same: remove one or report.
- `SubagentUnknown`: you did not start that agent with this tool. For other agents use `agents_ctl` (you cannot talk to them).
- `SubagentMissing`: someone else removed it; it is forgotten now and its slot is free.
- `SubagentQueued`: it still waits for a slot and has no stack yet; try again when `ls` shows it.
- `LetterDropped`: the subagent dropped that letter and will not answer it (not a valid message, blocked by its `before_queue` hook, or its CLI failed permanently after taking it); the reason is in the message. A temporary claude print API error keeps an ordinary letter pending for continuation after cooldown, rather than dropping it; a slash command is dropped even on a temporary error. Send it again if it still matters.
- `AnswerMissing`: no answer in time. Run `state`: `stopped` with a reason means it crashed (see `aos/status.md`); `running` or `stuck` means it is slow: `listen` later, or with a longer `timeout_s` / `timeout_cycles`.
- `ToolMissing`: the `self_*` tool for that op is not installed next to this one.
- `ArgumentsBad`: that op does not take a key you gave, or a value has the wrong type; the message lists what it takes.

Remove subagents when you are done with them. Nobody removes them for you.

# subagent add: more options

`{"op": "add", "def": "defs/helper", "name": "kid"}` is enough. Optional keys (`agents_ctl` add takes the same):

- `ws`: its workspace, relative to yours (created if missing; default: yours). `stack`: its stack folder (default: one under your daemon).
- `def_json`, `ws_json`, `stack_json`: instead of `def`, `ws`, `stack`, a value kept as written and looked up again on every start, like `{"$env": "AOS_HOME", "$path": "/templates/agent-fsm"}`.
- `limits`: resource limits, like `{"mem_mb": 512, "files": 256}`. `mem_mb`, `cpu_s`, `file_mb` and `files` (open files; the key is not `nofile`) are per process: every tool run or brain call is a new process with its own count, so `cpu_s: 2` does not stop an agent from using minutes of CPU in total. `procs` counts the processes of the same user. `mem_total_mb` and `procs_total` cap the whole agent and all it starts (cgroup; without one the daemon warns and lists them in `limits_ignored`). `user` runs it as another account. There is no total-CPU key yet.
- `envs`: environment values for it, like `{"LANG": "C"}` (strings). An agent-fsm needs `AOS_LLM_KERNEL`: it gets the daemon's environment, not yours, so if the daemon has none, pass yours in `envs` (`{"AOS_LLM_KERNEL": "..."}`); without it the agent stops at once with LlmKernelMissing.
- `AOS_PARENT_STACK` and `AOS_NOTIFY_BOX` in `envs`: every subagent add records who asked (your root stack, even when the call comes from your tool or hook cell) and where its notices go (default: your `<stack>/mailbox`; `""` = none; another mailbox folder = there, like `{"AOS_NOTIFY_BOX": "/home/.../procs/xiaosi/mailbox"}`). Both must be absolute without `..`. brain_notify sends brain-failure notices there: kernel refusals and claude CliFailed / ReplyMissing events with a boolean retry field (temporary continuation or permanent stop). Codex events without that boolean stay silent. Work reports still follow the reply_to of your letter. `agents_ctl` add records them only when you give `envs` (`aos-agent ctl add`: `--envs`, `--parent`, `--notify-box`); an add without envs records nothing. To change the box later: `rm` (the stack stays), then `add` again with the same `stack` and new envs. The child reads both with `aos-agent ctl who --json` (`self_state` who): what the requester wrote, not proof.
- `auto_restart`: true = the daemon restarts it whenever it exits. Only for agents that stay up.
- `on_queued`: `fail` (the default) or `ok` when it still waits for a slot. Also taken by `start` and `wake`.
- `timeout_s`: seconds to wait for the daemon (default 30).
