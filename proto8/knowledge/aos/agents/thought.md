# Thoughts: one task, only the conclusion

Tool `thought` starts the agent definition given by required `from`, hands it one task and gives you back only its short conclusion; the helper's tool calls never enter your history.

When to use which:

- `thought`: one step of a plan, or "go look this up and give me one sentence". The helper is thrown away when it answers. You do not name it, talk to it again, or remove it.
- `agents`: a helper you want to keep talking to (several questions, a long job, its own definition). You name it, `ask` it, and must `rm` it yourself.

Call:

- do a step: `{"from": "helpers/basic", "goal": "Find what time it is and say whether it is morning"}`
- gather memory: `{"from": "helpers/basic", "goal": "From the knowledge base, find what endpoint packs are and give me one sentence", "tools": [{"name": "memory"}], "max_chars": 200}`
- a plan A -> B -> C: call `thought` once per step; put what earlier steps concluded into `context`, e.g. `"context": ["Step A concluded: the config is in cfg/"]`.

Rules:

- `from` is an agent definition folder, relative to your workspace or absolute; it must declare the `aos-agent` interface. The tool has no default definition. The helper receives `goal` and `context` as its task, on top of that definition. Say in `goal` what to bring back.
- Tools: omit `tools` to keep the definition's tools, pass `[]` for none, or list exactly those to keep. `{"name": "memory"}` without `path` lends it your own tool of that name; with `path` it gets that tool folder. Overrides follow the definition's `interfaces.json` declaration.
- Brain: yours, unless `endpoint` names another (e.g. cheaper) pack. Yours unreadable (e.g. in a sandbox) = error, often `InterfaceMissing`: pass `endpoint`.
- Depth is the launch environment parameter `AOS_THOUGHT_DEPTH` (unset means 0), passed to the helper as parent depth + 1. At depth 2, another call fails with `DepthExceeded`.
- `keep: true` keeps the helper, stopped (it does not use a loop); the answer then ends with `details: procs/<name>/` (relative to your daemon). To ask it more: `aos-agent ctl start --target <name>`, then `say` / `listen`.
- Errors: `AnswerMissing` = no answer within `timeout_s` (default 600; any finite positive number); the line ends with `(details: ...)`, the stack is kept for a human to inspect. `DepthExceeded` = a helper's helper may not start more helpers; do the step yourself. `ToolMissing` = you lent a tool you do not have. `ArgumentsBad` = `from` or `goal` missing or blank, or invalid arguments. `DaemonMissing` = no daemon, or it did not reply (busy, paused or down): do the step yourself or say so; try once more later at most. Do not retry in a loop.
