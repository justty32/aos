# Small thought: one task, just the conclusion

The `thought` tool starts a disposable child agent, gives it one task and returns only a short conclusion; the child's tool exchanges do not enter your history. The child definition comes from the call parameter `from`; only when omitted does it use the default in the tool registration's `env.AOS_THOUGHT_FROM`.

Choosing a tool:

- `thought`: one step in a plan, returning one sentence after checking. By default it is removed after answering; no naming, follow-up or manual removal is needed.
- `agents`: an assistant for an ongoing conversation. Name it, ask it questions, and `rm` it yourself.

Calls:

- With a configured default: `{"goal": "Find what time it is and say whether it is morning"}`.
- Choose another definition: `{"from": "helpers/reviewer", "goal": "Review the result and return one sentence"}`.
- Borrow your own tools: `{"goal": "Read the knowledge base and summarize endpoint packs", "tools": [{"name": "memory"}], "max_chars": 200}`.
- A → B → C: call once per step, passing the previous conclusion in `context`, for example `"context": ["Step A concluded: the config is in cfg/"]`.

Rules:

- Put the default in this agent's thought tool registration, for example `{"path": "../../lib/agent/thought", "env": {"AOS_THOUGHT_FROM": "helpers/basic"}}`. You can also use `--envs AOS_THOUGHT_FROM=helpers/basic` when registering the tool. The env value is passed literally, not resolved relative to the registry file; both `from` and this default resolve relative to your workspace `$AOS_WS`, while absolute paths are used as given. Store relative paths for portability. The definition must declare the `aos-agent` public interface. If neither is supplied, the result is `FromMissing`; no template is guessed. An explicitly blank value or wrong type gives `ArgumentsBad`, without falling back to the default.
- The child receives `goal` and `context` on top of its definition's existing settings. State clearly in `goal` what it should return.
- Tools: omitted `tools` keeps the definition's tool set; `[]` clears it; a list keeps only those tools. `{"name": "memory"}` without `path` borrows your own tool of that name; with `path`, that path is used. Overlays follow the definition's `interfaces.json` declarations.
- Brain: defaults to yours; `endpoint` can select another pack. If your brain settings cannot be read (for example, a sandbox cannot see the definition), an error is returned, commonly `InterfaceMissing`; you can supply `endpoint` explicitly.
- Depth is read from the startup environment's `AOS_THOUGHT_DEPTH` (unset means 0); the child starts with the parent's depth plus 1. Calling again at depth 2 gives `DepthExceeded`.
- `keep: true` stops and keeps the child after answering, appending `details: procs/<name>/` (relative to the daemon) to the conclusion. For a follow-up, first run `aos-agent ctl start --target <name>`, then `say`/`listen`.
- `AnswerMissing`: no answer within `timeout_s` (default 600; any finite positive number); the error line ends with `(details: ...)`, and the stack is kept for human inspection. `DepthExceeded`: the depth limit was reached; do this step yourself. `ToolMissing`: you do not have the same-named tool to borrow. `ArgumentsBad`: `goal` is missing or blank, or a parameter is invalid. `DaemonMissing`: `AOS_DAEMON` is unset or its directory does not exist. `DaemonFailed`: the daemon is configured and its directory exists, but no reply arrived within the timeout (it may be busy, paused or down). Do this step yourself or explain that it is temporarily unavailable; try at most once more later, without a retry loop.
