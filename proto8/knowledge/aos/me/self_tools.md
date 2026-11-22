# Changing your own toolbox

Tool `self_tools` is `aos-agent tools` aimed at you. It changes only your own tool list; your definition and other agents stay as they are. Changes work at once, in this turn: from your next reply you see the new list and call a new tool directly by its name (not in the same reply that added it).

One op per call (the JSON is the tool's arguments):

- list: `{"op": "ls"}`: one line per tool, its name and the first sentence of its description. `{"op": "ls", "long": true}`: one text line per tool with where it comes from, and the tools you turned off (kind `null`).
- show one in full (whole description, parameters, errors): `{"op": "get", "name": "math"}`. Use this when the one sentence from `ls` is not enough.
- add: `{"op": "add", "path": "tools/math"}` (all options: `aos/me/self_tools.md#/self_tools add: options`)
- remove: `{"op": "rm", "name": "math"}` (a name, else a path). This turns the tool off for you; its files stay.
- undo all your changes: `{"op": "reset"}`

Rules and errors: `aos/me/self_tools.md#/self_tools: rules and errors`.

# self_tools add: options

`{"op": "add", "path": "tools/math"}` adds the tool in that folder. Optional keys:

- `"name"`: the name to list it under (default: the folder name).
- `"replace": true`: replace a tool with that name.
- `"envs": {"LANG": "C.UTF-8"}`: fixed values for every call, stored as written. Not for secrets.
- `"env_file": "secrets/read.env"`: only its location is stored; it is read on every call. Use it for secrets.
- `"no_cache": true`: for executable tools.
- Instead of `path`: `"path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/base/math"}` keeps the path as written and looks it up on every use.

# self_tools: rules and errors

- Relative paths (`path`, `env_file`, a path in `rm`/`get`) start at your workspace: `tools/math` means `$AOS_WS/tools/math`. Absolute paths are used as they are.
- Adding a tool does not create it. The folder must already exist (`PathMissing` otherwise). Write the tool files in your workspace first, or ask a human.
- `ToolDefMissing`: the folder has no `_tooldef.json`, so it is not a tool. `ToolDefBad`: its `_tooldef.json` is broken. Make or fix it with `tools_def` (`aos/tools_def.md#/tools_def`); no stock template has `tools_def` (agent-fsm or eca): add it first with `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/tools_def"}}`.
- A tool whose path is gone or whose definition broke is shown by `ls` as `NAME TAB broken: CODE (...)` (kind `broken` with `"long": true`). It is not offered for calls; your other tools work as usual. Fix it with `{"op": "rm", "name": "NAME"}` and add it again from where it is now; `get` shows the full error.
- Moving a tool you added (for example `tools/x` to `new_tools/x`): `rm` it first, move the folder, then `add` the new path. The list keeps the old path until you do.
- `ToolExists`: a tool with that name is already there. Use `"replace": true` only if you mean to replace it.
- `ToolMissing`: no tool with that name (`rm`, `get`): `ls` first. `NameBad`: the name is empty or has a character a tool name cannot have.
- Unknown argument names, or an argument the op does not take, are `ArgumentsBad`.
- `DaemonMissing`, `DaemonFailed`, `InstanceMissing`: the feature is unavailable for now; say so, and try at most once more later (`aos/errors/common.md`).

Why it is safe: other agents started from the same definition do not see your change. A human can see what you changed with `aos-agent ctl state --target <you>` (line `tools   own: N listed, M set to null (…)`) and undo it with `aos-agent tools reset`.
