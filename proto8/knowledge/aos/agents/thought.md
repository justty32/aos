# Thoughts: one task, only the conclusion

Tool `thought` hands one task to a fresh helper agent and gives you back only its short conclusion; the helper's tool calls never enter your history.

When to use which:

- `thought`: one step of a plan, or "go look this up and give me one sentence". The helper is thrown away when it answers. You do not name it, talk to it again, or remove it.
- `agents`: a helper you want to keep talking to (several questions, a long job, its own definition). You name it, `ask` it, and must `rm` it yourself.

Call:

- do a step: `{"goal": "Find what time it is and say whether it is morning"}`
- gather memory: `{"goal": "From the knowledge base, find what endpoint packs are and give me one sentence", "tools": [{"name": "memory"}], "max_chars": 200}`
- a plan A -> B -> C: call `thought` once per step; put what earlier steps concluded into `context`, e.g. `"context": ["Step A concluded: the config is in cfg/"]`.

Rules:

- The helper knows only `goal` and `context`. Say in `goal` what to bring back.
- Tools: default only `clock`. `{"name": "memory"}` without `path` lends it your own tool of that name; with `path` it gets that tool folder.
- Brain: yours, unless `endpoint` names another pack (e.g. a cheaper one).
- `keep: true` keeps the helper, stopped (it does not use a loop); the answer then ends with `details: procs/<name>/` (relative to your daemon). To ask it more: `aos-agent ctl start --target <name>`, then `say` / `listen`.
- Errors: `AnswerMissing` = no answer within `timeout_s` (default 600); the line ends with `(details: ...)`, the stack is kept for a human to inspect. `DepthExceeded` = a helper's helper may not start more helpers; do the step yourself. `ToolMissing` = you lent a tool you do not have. `ArgumentsBad` = `goal` missing or blank. `DaemonMissing` = no daemon, or it did not reply (busy, paused or down): do the step yourself or say so; try once more later at most. Do not retry in a loop.
