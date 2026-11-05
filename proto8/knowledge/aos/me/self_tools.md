# Changing your own toolbox

Tool `self_tools`: add, remove or list your tools. It changes only your overlay; your definition stays as it is.

Call it like this (the JSON is the tool's arguments):

- add a tool: `{"op": "add", "name": "math", "path": "tools/math"}`
- replace a tool that already has that name: `{"op": "add", "name": "math", "path": "tools/math", "override": true}`
- remove a tool: `{"op": "rm", "name": "math"}`
- list your tools: `{"op": "ls"}` (one line of JSON)

Rules:

- `path` is a tool folder (it contains `_entry` and `_tooldef.json`). Write it relative to your workspace (`tools/math` means `$AOS_WS/tools/math`), or as an absolute path inside the tool library `lib/`. Anything else is `PathBad`.
- The change takes effect from your next turn. You will see the new tool in your tool list then, not in this turn.
- Adding a tool does not create it. The folder must already exist (`PathMissing` otherwise). Ask a human or write the tool files in your workspace first.
- `ToolExists`: a tool with that name is already there. Use `override: true` only if you mean to replace it.
- `DaemonMissing` / `InstanceMissing`: you are not running under a daemon, so there is no table row to change. The feature is unavailable; say so.

Why it is safe: other agents started from the same definition do not see your change. A human can see what you changed with `aos-agent ctl state --target <you>` (line `tools overlay: N added, M removed`) and undo it with `aos-agent tools reset`.
