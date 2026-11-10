# Changing your own toolbox

Tool `self_tools`: add, remove or list your tools. It changes only your overlay; your definition stays as it is.

Call it like this (the JSON is the tool's arguments):

- add a tool: `{"op": "add", "name": "math", "path": "tools/math"}`
- replace a tool that already has that name: `{"op": "add", "name": "math", "path": "tools/math", "replace": true}`
- give the tool fixed environment values: `{"op": "add", "name": "read", "path": "tools/read", "envs": {"AOS_MEMORY": "/data/memory"}}`; for secrets point at a file instead, `"env_file": "secrets/read.env"` (only its location is stored; it is read on every call)
- remove a tool: `{"op": "rm", "name": "math"}`
- list your tools: `{"op": "ls"}` (one line of JSON)

Rules:

- `env_file` follows the same location rules as `path`. Unknown argument names are `ArgumentsBad`.
- `path` is a tool folder (it contains `_entry` and `_tooldef.json`). Write it relative to your workspace (`tools/math` means `$AOS_WS/tools/math`), or as an absolute path inside the tool library `lib/`. Anything else is `PathBad`.
- The change takes effect from your next turn. You will see the new tool in your tool list then, not in this turn.
- Adding a tool does not create it. The folder must already exist (`PathMissing` otherwise). Ask a human or write the tool files in your workspace first.
- `ToolExists`: a tool with that name is already there. Use `replace: true` only if you mean to replace it.
- `DaemonMissing`: `AOS_DAEMON` is unset or its directory does not exist. `DaemonFailed`: the daemon is configured and its directory exists, but no reply arrived within the timeout (busy, paused or down). `InstanceMissing`: the daemon has no table row for you. Either way the feature is unavailable for now; say so. Do not retry right away; you may try once more later.

Why it is safe: other agents started from the same definition do not see your change. A human can see what you changed with `aos-agent ctl state --target <you>` (line `tools   own: N listed, M set to null (…)`) and undo it with `aos-agent tools reset`.
