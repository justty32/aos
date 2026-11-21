# do_task: one task inside your own conversation, only its summary kept

Tool `do_task` lets you work on one task in your own conversation and then fold all that work into a short summary, so your history stays small. It works only in an agent-fsm body (an eca body such as claude or codex gets `BodyUnsupported`).

1. `{"op": "start", "task": "Find where the config is read"}`: this call is the mark (`task` is optional).
2. Work as usual: call tools, read, think.
3. `{"op": "end", "summary": "The config is read in cfg/load.py; it needs AOS_HOME."}`: every message after the mark, up to this call, becomes one message `[aos] summary: lines A-B, N messages. Task "..." ended: SUMMARY`. The `summary` is required; write in it every fact you still need later, including what others told you during the task: their letters and reminders are folded too, unless you add `"keep_others": true` to `end`.

`{"op": "status"}` lists your open tasks. Tasks may nest (at most 5 deep); `end` always closes the innermost.

Want a separate worker instead of folding your own work? Use `fork` (a copy of you) or `subagent` (`aos/agents/subagent.md`). Rules and errors: `aos/me/do_task.md#/do_task: rules and errors`.

# do_task: rules and errors

- What stays: the mark and its result, then your summary. Messages from others that came during the task (letters, `[aos] goal:` reminders, `[aos] new_mail` notices) are folded too by default; the result of `end` says how many. With `"keep_others": true` on `end` they are not folded: they stay, in order, after the summary. Your own `[aos] summary:` messages inside the task are always folded.
- The folded messages are kept in `history_removed.jsonl` next to your history, as with `self_history`.
- Open tasks live in your tool folder (`tools/do_task/tasks.json`): after a stop or a restart you are still in them; call `status`.
- Your `todo` list and your `goal` are not touched by `end`.
- If you remove or summarize the mark yourself (`self_history`), `end` closes the task without folding: `MarkerMissing`.
- `TaskMissing`: you are not in a task. `DepthExceeded`: end a task first. `ArgumentsBad`: no `summary`, `keep_others` not true or false, or a key the op does not take. `OpUnknown`: op is not start, end or status.
- `BodyUnsupported`: your body keeps tool calls outside your history (eca); use `fork` or `subagent` instead. `StateBad`: `tasks.json` is broken; a human must fix it.
- `DaemonMissing`, `DaemonFailed`, `InstanceMissing`: unavailable for now; say so, try at most once more later (`aos/errors/common.md`). Other errors come from `self_history`'s layer (`aos/me/self_history.md#/self_history: rules and errors`).
