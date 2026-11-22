# Hooks: run a program of yours when something happens to you

Tool `self_hook` is `aos-agent hook` aimed at you. A hook is a tool folder or an executable that runs when an event happens. It gets the event as one JSON object on stdin. Only your own hook list changes, from the next event. It comes in the events pack, which no stock template has (agent-fsm or eca): add it first with `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_hook"}}`.

One op per call:

- list: `{"op": "ls"}` (add `"long": true` to see condition, timeout and hooks you turned off)
- show one: `{"op": "get", "name": "guard"}`
- add: `{"op": "add", "event": "before_tool", "path": "hooks/guard", "condition": "peek_now_time"}`
- remove: `{"op": "rm", "name": "guard"}`
- back to your original hooks: `{"op": "reset"}`

The events and their fields: `aos/me/self_hook.md#/Hook events` (on_clock: `aos/me/self_hook.md#/The on_clock hook`). Options of add and how a hook answers: `aos/me/self_hook.md#/Hook options and answers`. Writing the program: `aos/me/self_hook.md#/Writing the hook program`; examples: `aos/me/self_hook.md#/Hook examples`. A job at a wall time (every day at 09:00): `aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`.
Hooks are not checked for loops: a hook that sends you a message triggers your queue hooks again.

Errors: ArgumentsBad, OpUnknown, PathMissing, HookExists (add `"replace": true`), HookMissing, HooksMissing, HooksBad, NameBad, DaemonMissing, DaemonFailed, InstanceMissing.

# Hook events

Events and their fields (every event also has `event`, `hook`, `stack`):

- `before_queue`: a message is about to enter your conversation (`letter`, `content`). Can change `content`, can drop the message. On agent-fsm a `/compact` message does not pass here; on an eca every message does, slash messages too.
- `after_queue`: a message entered your conversation (`letter`, `content`).
- `before_tool`: one of your tools is about to run (`name`, `id`, `arguments`). Can change `arguments`, can block the call. On an eca only aos tools called through aos-mcp pass here (not the CLI's own tools), and a failing hook makes that one call an error result instead of stopping you.
- `after_tool`: a tool finished, before you see the result (`name`, `id`, `arguments`, `content`, `code`, `timed_out`). Can change `content`.
- `brain_failed`: your brain call failed (`name` = the error code, `reason`; `error` = the kernel's error object when there is one). A budget refusal comes as `name` `BudgetMissing` with the kernel's reason (not `BrainFailed`); you keep waiting and retry after a cooldown. Other kernel errors come as `name` `BrainFailed` with `code` (the kernel's code, when it gave one), `retry` (true: you keep waiting and retry; false: you stop), `attempt` (failures in a row), `status` (HTTP status, if any) and, when retrying, `wait_s` (seconds until the next try). `LlmKernelMissing`, `SendFailed` and `ReplyBad` carry only `name` and `reason`. For eca claude, `name` is `CliFailed` or `ReplyMissing`, with `code`, `retry`, `attempt`, `dropped`, `wait_s` when retrying, and `status` / `cause` when available. Temporary print API errors keep letters pending for a continuation prompt after cooldown; permanent errors stop and drop them. A temporary slash error drops only that slash letter and leaves an earlier retry record untouched. Codex keeps the old `name` / `reason` event without retry fields.
- `tool_added`: a new tool name appeared in your tool box (`name`, `path`).
- `before_compact`: your conversation is about to be compacted (`asked` = the words after /compact, `instructions` = extra summary instructions you may change, an empty string gives none, `restore` = null, text you may give to add back after the summary). Exit 10 blocks the compaction. On agent-fsm (a /compact with enough to fold, before old tool outputs are cleared) also `letters`, `mid_turn`, `foldable`, `clear` (true; set false to keep old tool outputs) and `summary` (null; give one and you are not asked, it is folded in at once); a blocked /compact gets the answer `compact blocked by hook ...` (in the middle of a turn it waits for the end of the turn and asks again); a failing hook is only a warning. On an eca with claude (its cli.json wires the template's compact_hook; Claude Code compacts) also `trigger` = `manual` for a /compact or `auto`; `instructions` there are what compact_hook gives Claude Code, `restore` is added right after the compaction, and a hook cannot write the summary.
- `after_compact`: the summary is ready (`summary`). On agent-fsm it is not in your history yet: also `letters`, `by` (`brain`, or the before_compact hook that gave the summary), `mid_turn`, `cleared` (old tool outputs cleared) and `restore` (what before_compact gave, else null); a hook may change `summary` and `restore` (a non-empty `restore` goes in as one user message `[aos] restored after compact: ...` right after the summary). On an eca with claude it only tells (`trigger`, `summary` = what Claude Code wrote).
- `after_start`: your loop started (also after a restart or a wake). `after_stop`: your loop is about to exit (stop, sleep, removal, a failure); not after a hard kill. The event has only `event`, `hook`, `stack`; the program reads the environment: `AOS_LOOP_CODE` (the code the loop exits with), `AOS_LOOP_SIGNAL` (the signal it got, or empty), `AOS_LOOP_CAUSE`: a code to match, `stop`, `sleep`, `remove`, `shutdown`, `stuck`, `signal`, `max`, `body_exit` or `error`, empty when not given (not the table's `reason`, which is a sentence for people).
- `before_run`: before each run of your loop: each state of a state-machine agent, each turn of an eca. Only when your definition's loop.json wires it (compiled with a hook on it, or the key added by hand); adding one to a loop.json without it gives a warning: it needs a recompile and a restart. The event has only `event`, `hook`, `stack`; the run number is in `AOS_LOOP_RUNS`, a state machine's state about to run in `STACK/stage.txt` (missing on the first run: the start state). No `condition`: to act on one state only, let the program read stage.txt. Exit 10 skips that run (the state does not run, you ask again after the loop interval). It costs a process on every run while wired; to do something on a timer use `on_clock`.
- `after_run`: after each run (wired the same way). Environment: `AOS_LOOP_RUNS`, `AOS_LOOP_RUN_CODE` (the run's exit code), `AOS_LOOP_RUN_SIGNAL` (or empty), `AOS_LOOP_RUN_MS`; a state machine's state now in `STACK/stage.txt`.
- On the four loop events (`after_start`, `after_stop`, `before_run`, `after_run`) the program's exit code goes to your loop as it is: any non-zero code stops your loop, except 10 on `before_run` (skip that run).
- `on_clock`: a clock moved on; see `aos/me/self_hook.md#/The on_clock hook`.

# The on_clock hook

- `on_clock`: a clock moved on (`clock`, `cycle`, `interval_ms`, `first`, `last_cycle`, `missed`). Give `every_cycles` or `every_ms` (ms are counted in clock cycles, not wall time: `every_ms` becomes ceil(`every_ms` / `interval_ms`) cycles, at least 1, so the real gap can be longer than written, not shorter); `clock` is optional (default: `AOS_CLOCK`; or a proc name / a path). `config` (any JSON, optional) is passed to the program as the event field `config`. Checked at the start of each of your steps; it runs once when due, however many were missed while you were busy (`missed` says how many), and not while you sleep. It also runs once right after you start, wake up or restart (field `first`: true, `last_cycle`: null, `missed`: 0).
- On eca a step is one pass of your loop (stock template: about three a second, also with an empty queue), not one answer. Nothing is checked while aos waits for the CLI to answer a queue message; the next check then runs the hook once.
- After a sleep the event does not tell you how long you slept or how many runs were missed. A handler that must catch up keeps its own record: `aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`.
- No clock (`AOS_CLOCK` not set and no `clock` key): the hook never runs. Your log gets one warning line `hook NAME (event on_clock) is not checked: AOS_CLOCK is not set ...`. Wall time is not used instead.

A `on_clock` hook shows you nothing: your conversation gets nothing from it. To hear about it, let its program send a letter to your queue: `aos-post send STACK/queue` with `{"role": "user", "content": "..."}` (STACK = the event's `stack`). Your definition may already have a `timer` hook (every 5 minutes, does nothing): replace it with your own program under the same name. It also has `mail_notify` (every minute, one message only when new letters came (also the ones that came while you slept); `aos/mailbox.md#/Hearing about new letters`).

# A job at a wall time (every day at 09:00)

`on_clock` counts clock cycles, not wall time. For "every day at 09:00" or "every 3 days", let the hook run every minute and let its program look at the wall clock itself. It sends one letter to your queue only when a job is due; otherwise nothing enters your history and no brain turn is spent.

File `hooks/daily` (then `chmod +x hooks/daily`):

```python
#!/usr/bin/env python3
# daily - on_clock hook: jobs at a local wall time; one letter to my queue when one is due
import datetime, json, os, subprocess, sys
JOBS = [{"name": "patrol", "at": "09:00", "every_days": 1, "text": "Morning patrol is due."},
        {"name": "status", "at": "09:00", "every_days": 3, "text": "The 3-day status update is due."}]
ev = json.load(sys.stdin)
state = os.path.join(os.environ["AOS_STACK"], "done.json")      # $AOS_STACK = this hook's own folder
try:
    with open(state) as f:
        done = json.load(f)                                     # {"patrol": "2026-11-13"} = the day it last ran
except (OSError, ValueError):
    done = {}
now = datetime.datetime.now()                                   # local wall time
due = []
for job in JOBS:
    last = done.get(job["name"])
    if last and (now.date() - datetime.date.fromisoformat(last)).days < job["every_days"]:
        continue                                                # ran recently enough
    if now.strftime("%H:%M") < job["at"]:
        continue                                                # too early today
    due.append(job)
if not due:
    sys.exit(0)                                                 # no letter: your history does not grow
text = "[daily] " + now.strftime("%Y-%m-%d %H:%M") + "".join(
    "\n- %s: %s (last ran: %s)" % (j["name"], j["text"], done.get(j["name"], "never")) for j in due)
r = subprocess.run(["aos-post", "send", os.path.join(ev["stack"], "queue")],
                   input=json.dumps({"role": "user", "content": text}), text=True, capture_output=True)
if r.returncode != 0:
    sys.stderr.write("daily: cannot send: %s\n" % r.stderr.strip())
    sys.exit(1)                                                 # done.json not written: tried again at the next check
for j in due:
    done[j["name"]] = now.date().isoformat()
with open(state + ".tmp", "w") as f:
    json.dump(done, f)
os.replace(state + ".tmp", state)
```

Add it: `self_hook` `{"op": "add", "event": "on_clock", "every_ms": 60000, "name": "daily", "path": "hooks/daily", "timeout_ms": 10000}`.

When a job is due you get one message like `[daily] 2026-11-13 09:00` and one line per job, `- patrol: Morning patrol is due. (last ran: 2026-11-12)`.

After a sleep, and the `first` run:

- The program does not read `first` or `missed`. It asks the same question at every check: is the time past `at` today, and did this job run within the last `every_days` days? Its record is `done.json` in the hook's own folder, which stays through sleep and restart.
- You wake at 10:00 and yesterday's 09:00 run was missed: the first check sends the letter at once, and `last ran` shows the gap.
- However many days were missed, each job is sent once, not once per missed day.
- You wake before `at`: nothing is sent until `at`.
- `every_days` counts from the day the job really ran: a late run moves the next one.
- The letter cannot be sent: exit 1, `done.json` is not written, the next check tries again (a failing on_clock hook is one warning line in your log).
- `done.json` is gone: every job counts as never run and is sent once when its time has come.
- Times are the local time of the machine. The letter waits in your queue like any message.

# Hook options and answers

Options of add: `path_json` (instead of `path`: a value kept as written, like `{"$env": "AOS_HOME", "$path": "/lib/x"}`; then give `name`), `name` (default: the file or folder name), `condition` (only for this tool name on `before_tool`, `after_tool`, `tool_added`, or error code on `brain_failed`; on other events it is kept but not compared), `timeout_ms` (default 60000; 0 = no limit), `replace` (true = replace a hook with the same name; the new entry has only what you give now, so give `config` again), `config` (`on_clock` only: any JSON kept in the entry; the program gets it as the event field `config`; `null` = not given. With `replace`, look at the old entry first (`{"op": "get", "name": "context_wrap"}`) and give the whole config again: agent-fsm's context_wrap has `"wrap": false`. Example for an eca, the context_wrap limit at 50%: `{"op": "add", "event": "on_clock", "every_ms": 5000, "name": "context_wrap", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/context_wrap"}, "config": {"percent": 50}, "timeout_ms": 20000, "replace": true}`).

How a hook answers:

- exit 0 and nothing on stdout: nothing changes.
- exit 0 and a JSON object on stdout, only on `before_queue`, `before_tool`, `after_tool` (there anything else on stdout = failure): `{"content": "..."}` or `{"arguments": {...}}` replaces that field. On agent-fsm's `before_compact` it may set `instructions`, `clear`, `summary`, `restore`, on `after_compact` `summary`, `restore`; on an eca's `before_compact` `instructions`, `restore` (aos/me/compact.md). On the other events stdout is not read.
- exit 10 on `before_queue` / `before_tool`: block it (the message is dropped; the tool does not run and you get the hook's stdout as the result. A blocked call is not marked as an error: the result looks like a normal answer, so let the hook print clearly that it blocked the call). On `before_compact`: no compaction. On `before_run`: skip that run. On after_start, after_stop and after_run it is a non-zero code like any other: the loop stops. On the other events 10 counts as 0.
- any other exit code, a timeout, or a bad stdout: the hook failed. On `before_queue` and `before_tool` you stop (HookFailed; on an eca a failing `before_tool` hook only makes that call an error result); on the other events it is one warning line; on the four loop events your loop stops.
- With several hooks on one event they run in name order; on the events your body fires itself each sees what the earlier ones changed, agent-fsm's `before_compact` and `after_compact` too (on the four loop events and an eca's compact events each gets the same event).

# Writing the hook program

The program (`path` in add) can be:

- an executable file (`chmod +x`; a script starts with `#!/usr/bin/env python3` or `#!/bin/sh`);
- a JSON file `{"argv": ["python3", "x.py"]}` with `x.py` next to it (no chmod needed);
- a tool folder with an `_entry`.

A plain file that is not executable fails (`EntryBad` in your log).

What it gets:

- stdin: one JSON object: `event`, `hook` (its name), `stack` (your stack), and the event's fields (`aos/me/self_hook.md#/Hook events`).
- `$AOS_STACK` = the hook's own folder `<your stack>/hookeds/<name>/`. Files it writes there stay for its next run. Your own stack is the `stack` field, not `$AOS_STACK`.
- `$AOS_WS` = your workspace. The current folder = the folder the program is in. Your other `AOS_*` variables are set too (`AOS_DAEMON`, `AOS_CLOCK` ...).
- Its stderr goes where yours goes (under a daemon: `stderr.txt` in your stack). Its stdout counts only on `before_queue`, `before_tool`, `after_tool`; its exit code on the loop events goes to your loop (`aos/me/self_hook.md#/Hook options and answers`).

To reach your brain, send a letter to your queue: `aos-post send STACK/queue` with stdin `{"role": "user", "content": "..."}`. A full program: `lib/tools/agent/mail_notify` under `$AOS_HOME` (`aos/mailbox.md#/The mail_notify hook`). Short ones: `aos/me/self_hook.md#/Hook examples`.

# Hook examples

- Log every stop and start. File `hooks/up_down` (then `chmod +x hooks/up_down`):

```
#!/bin/sh
cat >> "$AOS_WS/up_down.log"
echo " code=$AOS_LOOP_CODE signal=$AOS_LOOP_SIGNAL cause=$AOS_LOOP_CAUSE" >> "$AOS_WS/up_down.log"
```

  `self_hook` `{"op": "add", "event": "after_stop", "name": "down", "path": "hooks/up_down", "timeout_ms": 5000}`, and the same with `after_start` and name `up` (there the three variables are empty). A stop logs `code=0 signal=`; sleep, removal or a daemon shutdown log `code=143 signal=15`. A hard kill (kill -9) logs nothing. Let it exit 0: a non-zero exit on these events stops your loop.
- Keep `timeout_ms` of `after_start` / `after_stop` at 5000 or less: the loop waits at most 5 seconds for them.
- Block a tool: a `before_tool` program with `"condition": "shell"` that prints a reason and exits 10. The tool does not run; you get the reason as its result.
- Every 10 minutes, a program alone: `{"op": "add", "event": "on_clock", "every_ms": 600000, "path": "hooks/backup"}`.
- Every day at 09:00, or every 3 days (wall time): `aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`.

# Eca screen lifecycle hooks

The stock eca hooks screen_linger_start (after_start, first) and screen_linger_stop (after_stop) cancel or schedule delayed screen closure. They use the event's stack, not the handler's AOS_STACK. Both have a 4000 ms timeout; their own errors are only a warning line (they exit 0), so they never stop your loop. cli.json screen_close_after_s is a non-negative integer in seconds (default 600, 0 closes immediately). Set both hook names to null in your stack copy to keep screens indefinitely. Starting or waking cancels pending orders; pausing does not schedule one. A new live loop is protected even if the start hook fails. Attached viewers are disconnected at expiry. Hard kills and screens opened after stopping have no fallback. Details: `aos/cli/eca.md#/Delayed screen closure`.
