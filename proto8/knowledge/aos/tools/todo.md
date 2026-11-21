# Tool todo

Your own to-do list for a long task. It is kept in your stack, not in your history: after a summary it is still there. It is not put into your prompt by itself: call `ls` to see it again.

Use it when a task has 3 or more steps: write the steps first, mark one `in_progress` when you start it, `completed` when it is done; keep at most one `in_progress`. One op per call; every op prints the whole list:

```json
{"op": "set", "items": ["read the config", "write the parser", "add tests"]}
{"op": "mark", "n": 1, "status": "completed"}
{"op": "mark", "n": 2, "status": "in_progress"}
```
prints
```text
1 [x] read the config
2 [>] write the parser
3 [ ] add tests
... 1 of 3 completed
```

An empty list prints `... empty (use set or add)`.

The ops (ls, set, add, mark) and limits: `aos/tools/todo.md#/todo: ops`. Where it is saved, other agents' lists: `aos/tools/todo.md#/todo: where the list is`. Errors: `aos/tools/todo.md#/todo: errors`.

# todo: ops

- `ls`: print the list; it never writes anything. `"json": true` prints one JSON object: `items` (each `n`, `text`, `status`), `counter_completed`, `updated_at` (UTC; null before the first write).
- `set`: replace the whole list with `items`. An item is a string (status `pending`) or `{"text", "status"}`; both may be mixed. `[]` clears it. There is no remove op: `set` the list without that item, then read the new numbers.
- `add`: add `text` as `pending` at the end; `"after": N` puts it after item N, `0` at the top.
- `mark`: set item `n` (from 1) to `status`: `pending`, `in_progress` or `completed`.

Marks: `[x]` completed, `[>]` in_progress, `[ ]` pending. Two or more in_progress add a line `... note: 2 items are in_progress (keep at most one)`.

Limits: at most 50 items; each text one line, at most 300 characters (spaces at both ends dropped). More is `ArgumentsBad`; nothing is cut.

# todo: where the list is

- In your tool cell: `<your stack>/tools/todo/todo.json`, made on the first write. Registered under another name, the cell has that name: a different list.
- A finished list stays until you `set` a new one.
- Each agent has its own list: a subagent has its own stack and list, and cannot see yours (nor you theirs). `do_task` folding your history does not touch the list.
- One call at a time: two calls running at the same moment (two `add` called in parallel) may lose one change.

# todo: errors

- `ItemMissing`: `n` (or `after`) is not on the list; the message says how many items there are. Call `ls`, then use a number from it.
- `StatusUnknown`: the status is not `pending`, `in_progress` or `completed` (for example `done`). Use one of the three.
- `ListBad`: the saved list (`todo.json`) is broken, maybe changed by hand. `ls`, `add` and `mark` stop; `set` still works and writes a new whole list.
- `OpUnknown`: op is not `ls`, `set`, `add` or `mark`.
- `ArgumentsBad`: no op, a key the op does not take, empty or multi-line text, over 300 characters, over 50 items, `n` or `after` not a whole number, `json` not true or false, an item with keys other than `text` and `status`, `mark` without `n` or `status`, `add` when the list already has 50 items.
- `StackMissing`: AOS_STACK is not set; the tool runs through aos-tools call (what your body does).
- `ReadFailed`, `WriteFailed`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys: `aos/errors/common.md#/Codes about what you gave`.
