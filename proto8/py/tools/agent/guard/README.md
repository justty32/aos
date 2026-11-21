# guard: before_tool guard for file, shell, mail and control tools

> **Status: under review. Do not mount this hook to restrict agents yet.** An independent review found ways around some checks; fixes are in progress. It is not wired into any shipped definition or kit.

`guard` is a before_tool hook handler (python3, stdlib only). It reads the tool call on stdin (`{"name": ..., "arguments": {...}}`) and answers with its exit code:

| exit | meaning |
|---|---|
| 0 | allowed (nothing on stdout) |
| 10 | blocked: one line `[aos] guard: blocked: ...` on stdout, which the agent sees as the tool result. Also when an argument has a wrong type or shape (the agent can fix it and call again) and when the daemon table cannot be read (see "Write scope") |
| 1 | error: one line `guard: error: CODE reason` on stderr (`CfgMissing`, `CfgBad`, `ArgumentsBad`, `WsMissing`): a broken config or event. A failing `before_tool` hook stops the event (the agent family's rule since 11-21): the call does not run, and the whole agent stops (not only this call) |

It checks: file-tool paths against the write scope (below) and the path rules (`deny_parts`, `proc-stack`, `definition-marker`, `no-hash-outside-json`, `no-tilde`); mail `keep` files like write paths; shell commands (`shell_deny` regexes, with the relaxed check below); `subagent` ops; `clock_register` boxes and daemon; `mailbox_send` boxes, names and daemon; `kernel_gate` ops; `agents_ctl` (ring the bell: stop yourself only). Every other tool name is blocked.

Derived from fsm-guard (commit 313ce20ec): same checks and the same tests (they hold the bypasses found in the review rounds), with neutral messages and one source for the write scope.

Files: `_entry` (the hook handler; `_entry --scope` prints the write scope), `guard.py` (the checks, importable), `scope.py` (the write scope, importable; `python3 scope.py` prints it), `tests/`.

## Tools it knows

The guard has a rule for exactly these tool names (`guard.KNOWN_TOOLS`):

| tool | what is checked |
|---|---|
| `write`, `edit`, `mkdir`, `trash`, `remove`, `ws_write` | `path`: write scope and path rules |
| `copy` | `to`: write scope and path rules; `from` (read only): only `no-hash-outside-json` and `no-tilde` |
| `move` | `from` and `to`: write scope and path rules |
| `json_set`, `json_add`, `json_del` | `path` = `FILE#/POINTER`: FILE is checked; an empty FILE is blocked |
| `json_multi_set` | each `items[].path`, like `json_set`; no items is blocked |
| `mailbox_read` | `keep`: `true` / `false` / absent is not a path; a file name gets the write check |
| `mailbox_send` | `keep`: a file name gets the write check, `true` is blocked; `box` (mail rules below: only the own tree); `to` (`mail_allow_to`); `daemon` (own daemon only) |
| `clock_register` | `box` (`clock_boxes`); `daemon` (own daemon only) |
| `subagent` | the config's `subagent` rule |
| `shell`, `run_python` | `shell_deny`, relaxed check for `shell` |
| `kernel_gate` | the config's `kernel_gate` rule |
| `agents_ctl` | the config's `agents_ctl` rule |

Any other name (a tool added later, a made-up name, a missing name) is blocked with `guard has no rule for this tool (...); remove it from the hook's condition or add a rule.` The guard goes by the tool name the agent called, not by the program it runs.

Not known on purpose: the `jsonx_*` tools. They can follow `$ref` links from the file named in the call into other files, so the file the guard would check is not the only file they may write; until a rule resolves those links the same way, they stay blocked. Read-only tools (`read`, `ls`, `grep`, `json_get`, ...) have no rule either: they need no guard, so leave them out of the condition.

Tools in the shipped packs that can change files or the agent itself and have no rule (do not give them to an agent the guard is meant to hold, or leave them unguarded knowingly): `agent_def`, `tools_def` (create definition and tool folders at a path), `self_hook` (changes the agent's own hooks, the guard entry included), `self_tools` (adds tools to the agent), `self_history` (its `keep` names a file), `self_system`, `self_llm`, `self_ctl`, `fork` (starts a new proc from a copy of the agent), and the `jsonx_*` writers. `board_set`, `board_clear` and `do_task` have no rule either; they change only the agent's own board and tasks.

## Mount it

hookeds.json of the definition (or a stack copy written by `self_hook`):

    "guard": {"event": "before_tool",
              "condition": ["write", "edit", "copy", "move", "mkdir", "trash", "remove", "json_set", "json_add", "json_del", "json_multi_set", "mailbox_send", "mailbox_read"],
              "handler": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/guard"},
              "timeout_ms": 10000}

Always mount it with a `condition`, and list in it only tools from the table above that the kit gives: add `ws_write`, `shell`, `run_python`, `clock_register`, `subagent`, `kernel_gate`, `agents_ctl` only if the agent has them (see "Known limits" for the last two). A tool in the condition that the guard does not know is blocked on every call; a writing tool left out of the condition is not checked at all. The hook must be `before_tool`: only there exit 10 blocks the call, and a broken config (an error, exit 1) stops the event instead of letting the call through. Remove the guard = drop the hook entry.

The hook runs with the agent's environment, except that `AOS_STACK` is the hook's own cell `<stack>/hookeds/guard/` and `AOS_CD` is this folder. Put `AOS_GUARD_CFG`, `AOS_WRITE_ALLOW` and `AOS_WRITE_DENY` in the agent's environment (the definition's `.env`, or `aos-agent ctl add --envs`).

## Write scope (scope.py)

One source, read the same way by the guard and by anything else (`python3 scope.py` or `_entry --scope`; in Python `scope.write_scope(env=None)`). Shape, version 1:

    {"version": 1,
     "allow": [{"path": "/abs/ws", "from": "AOS_WS"}, {"path": "/abs/b", "from": "AOS_WRITE_ALLOW"}],
     "deny":  [{"path": "/abs/stack", "from": "AOS_STACK"}, {"path": "/abs/guard", "from": "AOS_CD"},
               {"path": "/abs/def", "from": "definition"}, {"path": "/abs/other/stack", "from": "daemon-table"},
               {"path": "/abs/other/def", "from": "daemon-table"}, {"path": "/abs/daemon", "from": "AOS_DAEMON"},
               {"path": "/abs/product/lib", "from": "AOS_HOME"}, {"path": "/abs/s", "from": "AOS_WRITE_DENY"},
               {"path": "/abs/x", "from": "guard.json"}],
     "deny_parts": [".git"],
     "rules": [{"name": "deny_parts", "parts": [".git"]}, {"name": "proc-stack"},
               {"name": "definition-marker", "marker": "interfaces.json"},
               {"name": "no-hash-outside-json", "json_tools": ["json_set", "json_add", "json_del", "json_multi_set"]},
               {"name": "no-tilde"}]}

Exit 0 with that object on stdout (one line); exit 1 with `scope: error: CODE reason` on stderr. Keys:

- `version`: 1. It changes when the meaning of a key changes or a rule is added. A reader (for example a shell sandbox) should refuse a version it does not know, and a rule name it does not know.
- `allow`, `deny`: absolute, resolved (realpath) folders with their source. A deny entry appears once (the first source wins).
- `deny_parts`: the configured list of path parts (default `[".git"]`), also given as the `parts` of the `deny_parts` rule.
- `rules`: checks that are not a fixed list of folders; the guard applies them to each path, and a sandbox reading the scope must apply them too (in Python `scope.proc_stack(realpath)`, `scope.definition_marker(realpath)`).

A file-tool path may be written when it passes, in this order: `no-tilde` and `no-hash-outside-json` (on the path as written), then on its realpath `deny_parts`, the deny list, `proc-stack`, `definition-marker`, and finally it must be at or under an allow path.

- allow: `realpath($AOS_WS)` always, plus each entry of `AOS_WRITE_ALLOW` (separated by `:`, the OS path separator).
- deny, none of which the config can lift:
  - `AOS_STACK`: the agent's own stack (a hook or tool cell `<stack>/hookeds/<name>` or `<stack>/tools/<name>` counts as `<stack>`, so the whole stack of the agent is denied, not just the cell);
  - `event` (the guard only; `--scope` reads no event): the `stack` field of the hook event, cut the same way. The hook runner writes it (`hook_run.py`), and the agent's arguments cannot change it; a value that is not a path string blocks the call;
  - `AOS_CD`: when set (in a hook: this folder);
  - `definition`: the `def` of the row in `$AOS_DAEMON/procs_state.json` whose `stack` holds `AOS_STACK` (the deepest such row, as `aos-agent ctl who` does);
  - `daemon-table`: the `stack` and the `def` of every row of that table, the agent's neighbours included (shards `{"$ref": [...]}` are joined; relative values count from the daemon folder). The table is read whether or not `AOS_KERNEL` is set. The daemon writes every row as an object whose `stack` is a non-empty string and whose `def` is a string or `null` (a path given as a directive, `--stack-json` / `--path-json`, is kept in the row's `as_written`; `stack` and `def` hold the resolved path: aos-daemon `row()` in `src/child/child.cpp`, `fix_path` in `src/daemon/procs.cpp`). So a table file that exists but cannot be parsed, has a missing shard, or has a row of another shape is read once more after 50 ms (the main file and its shards are written one by one, as `daemon_ctl` also retries); if it is still bad, every call that needs the table is blocked (`the daemon table ... cannot be read ... Try once more`, exit 10) and `--scope` fails with `TableBad`. No table file at all (the daemon has not started, or `procs_state` is off) = no rows: only the other entries and the rules below apply;
  - `AOS_DAEMON`: the whole daemon folder (`realpath($AOS_DAEMON)`), with its control files, even when its table is missing;
  - `AOS_HOME`: when set, `lib`, `templates`, `knowledge`, `cpp`, `py`, `bin` and `include` under `realpath($AOS_HOME)` (only those that exist);
  - `AOS_WRITE_DENY`: each entry, separated like `AOS_WRITE_ALLOW`;
  - `guard.json`: the config's `deny_roots`.
- rules, which no config lifts (not `deny_roots` or `AOS_WRITE_ALLOW`; `deny_parts` is the config's own list):
  - `deny_parts`: a path part equal to one of the parts (default `.git`);
  - `proc-stack`: a path whose realpath is inside a stack laid out in one of three ways, found without the daemon table. Walking up the realpath (missing tail parts hold no file), the deepest of these is the stack: a path part named `.stack` (the default stack of `aos-exec` / `aos-mcp` is `WS/.stack/`, and the CLI takes `./.stack` as the daemon); a folder holding `procs_state.json` (a daemon stack, all of it); a folder D whose parent is named `procs` and whose grandparent holds `procs_state.json` (a proc stack, default `<daemon stack>/procs/<name>/`; a not-yet-made `procs/<new>/` counts). A folder named `procs` with no `procs_state.json` above it is ordinary. A stack placed elsewhere (`--stack DIR`) is not recognised by this rule: only the daemon table (`daemon-table`) names it, so with `AOS_DAEMON` unset or no table file such a neighbour's stack is not denied;
  - `definition-marker`: a path at or under a folder holding `interfaces.json` (an agent definition), also without the daemon table (every definition has it: `aos-agent` reads the other files through it). Programs a definition runs from outside its folder (a tool folder named in `tools.json`, a hook handler) are not covered: keep them where no guarded agent can write;
  - `no-hash-outside-json`: a `#` in a path is blocked, except in the json tools, which cut `FILE#/POINTER` at the first `#` (the other tools take the whole string as a path);
  - `no-tilde`: a tool path starting with `~` is blocked (`use an absolute path or one relative to AOS_WS`): the tools do not expand `~`.
- A tool path is placed the way the tool places it: relative = from `AOS_WS`, then symlinks and `..` are resolved. A link inside the workspace that points outside it is judged by where it points. For tools that act on the entry itself (`trash`, `remove`, `copy`, `move`) the entry (its folder resolved, plus its last part) is checked as well as where a final link points; both must pass. Only the path and the folders above it are checked, never what is inside it: `remove`, `trash` or `move` of a folder that holds a denied folder (a neighbour's stack, a definition, `.git`) passes when the folder itself may be written. Do not give these tools to an agent the guard is meant to hold (see "Known limits" o).
- Environment and config entries (`AOS_WRITE_ALLOW`, `AOS_WRITE_DENY`, `deny_roots`, `clock_boxes`, `mail_deny`, the `subagent` def and ws of the config) are read the same way, except that `~` or `~/...` is the home folder (`HOME`; `~user` is not expanded).
- Block messages name the rule or source: `... is outside the folders you may write (AOS_WS=/a, AOS_WRITE_ALLOW=/b) ...`, `... is inside a folder no agent may write (/s, from daemon-table) ...`, `... is inside a proc's stack (/d/procs/bo, rule: proc-stack) ...`, `... is inside an agent definition (/x holds interfaces.json, rule: definition-marker) ...`.
- A config with a `write_roots` key is refused (`CfgBad`, exit 1, for every tool call): move those folders to `AOS_WRITE_ALLOW`.

### What a sandbox misses if it reads only --scope

The scope is a snapshot of the folders and rules for file writes. A sandbox (or anything else) that applies only `--scope` does not get:

- the rules that look at files when a path is checked: `proc-stack` and `definition-marker` find stacks and definitions by walking up each path, so a stack or definition made after the scope was printed is caught by the guard but not by a fixed list of folders; likewise `deny_parts` matches a part anywhere (a `.git` made later). A sandbox must apply the rules itself, or print the scope again;
- later changes to the daemon table (a new row's stack and definition) and `AOS_HOME` folders that did not exist when the scope was printed;
- the checks that are not about file paths: mail `box`, `to` and `daemon`, `clock_register` boxes and daemon, `subagent`, `kernel_gate`, `agents_ctl`, `shell_deny`, and the block of tools the guard has no rule for;
- `no-hash-outside-json` and `no-tilde` are about how the tools read their path arguments; a program that opens a path itself does not need them;
- `AOS_STACK` is cut by one cell level (`<stack>/hookeds/<name>` or `<stack>/tools/<name>`); a scope printed from a deeper cell (a tool called by a tool) lists that cell, not the whole stack, unless the daemon table or `proc-stack` names the stack.

## Config (guard.json)

The file named by `AOS_GUARD_CFG`. Unset or empty = no config (the defaults below). Set but not a file = `CfgMissing`; not JSON or not an object = `CfgBad`.

Keys: `deny_roots` (list), `deny_parts` (default `[".git"]`), `shell_deny` (regex list, `re.search` over the whole command), `subagent` (`ops`, `def`, `ws`, `name` regex; no `name` = any name), `clock_boxes` (list), `mail_deny` (list), `mail_allow_box` (list), `mail_allow_to` (regex), `mail_foreign_queue` (`"deny"` or `"allow"`), `kernel_gate` (`ops`), `agents_ctl` (`ops`, `self_only`, `max_timeout_s`). A key of the wrong type (a list that is not a list of non-empty strings, a regex that does not compile, a rule that is not an object, `subagent` without a `def` path) = `CfgBad` for every tool call.

Defaults: no `shell_deny` key = `shell` and `run_python` are blocked (an empty list `[]` is a rule: nothing denied); no `subagent`, `kernel_gate` or `agents_ctl` rule = that tool is blocked; no `clock_boxes` = `clock_register` may only wake the agent itself; no `mail_allow_box` = a `box` only on the own tree (below); no `mail_allow_to` = any name; no `mail_foreign_queue` = `"deny"`.

## Mail (`mailbox_send`, `mailbox_read`)

- `keep`: a string is a file the tool appends to (and creates), placed from `AOS_WS`: it gets the same check as a `write` path. `mailbox_read`: `true`, `false` or absent is not a path (`true` archives into the agent's own mailbox). `mailbox_send`: `false` or absent = no keep; `true` is blocked (the tool has no such mode: it would pass `true` on as a file name). Any other type is blocked.
- `daemon` (`mailbox_send`, and `clock_register`): allowed only when absent or when its realpath equals `realpath($AOS_DAEMON)`; with `AOS_DAEMON` unset any `daemon` is blocked.
- `box` given: it must be on the agent's own tree. Its real path must be at or under one of: `<stack>/mailbox` of a row on the own daemon's table (`$AOS_DAEMON/procs_state.json`, the same rows as `daemon-table`); the agent's own `<stack>/mailbox` and `<stack>/queue` (from `AOS_STACK` and the event's `stack`); with `"mail_foreign_queue": "allow"` also `<stack>/queue` of every row; the workspace (`realpath($AOS_WS)`); an entry of `mail_allow_box`. Anything else is blocked (`a box must be the mailbox of a proc on your own daemon's table, a folder in your workspace, or one listed in the guard config (mail_allow_box)`): another tree's or another daemon's agents, and the user zone (`~/.aos/user/`), which is allowed only when listed in `mail_allow_box`. A crew member's report to its lead passes: the `reply_to` of the lead's letter is `<lead stack>/mailbox`, and the lead is a row on the same daemon (if it is not, list its mailbox in `mail_allow_box`, or mail it by name). With `AOS_DAEMON` unset or no table file there are no rows, so only the agent itself, the workspace and `mail_allow_box` remain; an unreadable table blocks. `to` with no `daemon` always goes to the own daemon. Before that list, a `box` is blocked when its real path is at or under
  - a daemon ctl mailbox: a daemon stack is a folder with `procs_state.json`; its ctl mailbox is the folder named by that file's `procs_requests` key (default `procs_requests`). Any path part named `procs_requests` also counts, marker or not;
  - a kernel mailbox: any path part named `requests` (`<station stack>/requests`, `$AOS_LLM_KERNEL/requests`, `<stack>/hookeds/kernel_gate/requests`, `<stack>/hookeds/<gate>/requests`), or `$AOS_KERNEL` / `$AOS_LLM_KERNEL` when set;
  - another agent's queue: any path part named `queue` whose parent is not the agent's own stack (a letter there goes straight into that agent's conversation). The agent's own `<stack>/queue` is allowed. This is the only check that `"mail_foreign_queue": "allow"` turns off (default `"deny"`); the other three stay;
  - a `mail_deny` root.
- `to` given: blocked only when `mail_allow_to` is set and the name does not fully match it.
- The rule is by folder names, so a plain folder called `requests`, `procs_requests` or `queue` is refused too. A reply normally goes to the sender's `<stack>/mailbox`, which passes.
- `clock_register` agrees with this: its `box` is an allow-list. Without `box` it wakes the agent itself; with `box` the real path must equal one listed in `clock_boxes`. So `mailbox_send` blocks foreign queues by default (switch: `mail_foreign_queue`), and `clock_register` only allows the boxes listed in `clock_boxes` (a foreign queue only if it is listed there; `mail_foreign_queue` does not change `clock_register`).

## Relaxed shell check (tool `shell` only; `run_python` is always strict)

A command skips `shell_deny` only if it is "plain read-only" and the shell environment is trusted; anything else gets the whole-text regex check (its block message then says "strict check ..."). Plain read-only = all of:

- Quoting is tracked per character. Single quotes: literal. Double quotes: no `\`, no backtick, `$` only as `$NAME`.
- Unquoted: words of `A-Za-z0-9_./,:=@%+*?!~^-` and quotes (an unquoted `$NAME` is strict: bash splits it on IFS and globs it; write `"$NAME"`); separators `;` `|` `&&` `||` newline; the only redirections are the words `2>/dev/null`, `>/dev/null`, `2>&1`. Anything else (`\`, backtick, `#`, `{}`, `[]`, `()`, `<`, `>`, single `&`, `$(`, `${`, `$[`, `$'`, `$1`, `$_`, non-ASCII, CR, NUL or another control character anywhere, an unclosed quote, an empty command) = strict.
- Every simple command's first word is unquoted, matches `^[A-Za-z0-9_-]+$` and is one of: cat head tail wc grep egrep fgrep rg ls pwd cd echo printf true false test pgrep ps stat basename dirname realpath readlink du df cmp md5sum sha1sum sha256sum nl cut uniq tr column comm jq date id whoami uname which sort sed.
- An argument with an unquoted `*` or `?` must start with a literal other than `-` (a glob could expand to a planted file name like `--pre=sh`).
- rg, sed, sort, printf: no `$` in any argument. rg: every `--option` is in a fixed safe list (no `--pre`, `--hostname-bin`, `--search-zip`, ...), no short option cluster with `z`. sed: exactly `sed -n SCRIPT FILE...`, SCRIPT = `Np`, `N,Mp`, `N,$p` or `$p` (no spaces), no FILE starts with `-`. sort: options only clusters of `unrVhf`. printf: first argument does not start with `-` (`-v` assigns). uniq: no `$` or glob, no `-` or `--` argument, at most one argument not starting with `-` (`uniq IN OUT` writes OUT). date: no `$` or glob, every argument starts with `-` or `+`, no short option cluster with `s`, no `--s...` (`-s`, `-us`, `--set`, `MMDDhhmm` set the clock).
- Trusted environment (in the hook's environment, which the shell tool inherits): no `BASH_ENV`, `ENV` or `RIPGREP_CONFIG_PATH` set (even empty), no `BASH_FUNC_*` variable (an exported bash function), no relative or empty entry in `PATH`. Otherwise the strict check runs for every command and the block message says why.

Examples that pass: `rg -n 'rm accepted' x`, `pgrep -u "$USER" -af aos-daemon`, `sed -n '1,20p' f && rg --files . | rg 'aos-x'`. Not plain (strict): anything with git, xargs, find, interpreters, `$(...)`, `> file`.

## Stack overlay

The guard is only an entry in the agent's hookeds.json. An agent with `self_hook` can drop or replace it in its stack copy; one with `self_tools` can add a tool that does. A kit that relies on the guard must not give its agents `self_hook` or `self_tools`. (The guard denies file-tool writes to the agent's own stack, so the stack copy of hookeds.json cannot be changed with the file tools.)

## Known limits

a. Not a security boundary. The sandbox (aos-sandbox / bwrap) is the write boundary; the guard only stops slips. The deny list and the mail rule apply to tool calls, not to what a shell command writes (a shell sandbox can read the same list and rules with `_entry --scope`).
b. Regex gaps (handled only as "not plain read-only", not blocked): the strict `shell_deny` regex is whatever the config says. A regex over the command text cannot follow the shell: an example list like the one in the tests misses commands written with quotes, brace expansion, variables, line continuations, git's global options before the subcommand, or a program run through another one (xargs and the like). The tests hold the exact forms and check that they are not plain read-only, not that they are blocked; a kit that gives `shell` needs the sandbox as its write boundary.
c. Shell environment trust: the relaxed check is skipped when `PATH` has a relative or empty entry, or `BASH_ENV`, `ENV`, `RIPGREP_CONFIG_PATH` or a `BASH_FUNC_*` variable is set (see above); the block message names the variable, not its value. Other variables that change a program's behaviour (for example `LD_PRELOAD`) are not looked at; the sandbox bounds them.
d. Tool versions: the whitelist was reviewed against GNU coreutils 9, ripgrep 14, GNU sed 4.9, jq 1.7 and procps-ng. BSD tools or a newer rg may give options other meanings; `RG_LONG` is a fixed list and must be updated if rg adds options that run programs.
e. Deliberately allowed, not blocked: `cd` (changes the directory for later commands); `sort` writes temp files in `$TMPDIR` on large input; `df --sync` calls sync(2); `tail -f` hangs (until the tool's timeout). Reading is not limited: `cat` / `jq` / `copy.from` can read any file the tool may read, secrets included; that is not the guard's job.
f. Shell tool parameters other than `command`: only `command` (shell) and `code` (run_python) are looked at; the shell tool has only `command` and `timeout_s` today. If it gains `cwd`, `env` or similar, the guard must look at them.
g. TOCTOU: a path is resolved (realpath) when it is checked, so a symlink can be swapped between the check and the write; the sandbox is the backstop.
h. `kernel_gate` and `agents_ctl` are only checked when the hookeds.json entry's `condition` lists them; listing them without a rule in the config blocks them completely. The same holds for `subagent`, and for `shell` / `run_python` without `shell_deny`.
i. Mount: the guard only works mounted as described in "Mount it": `before_tool`, with a `condition`. On any other event it blocks nothing. Another `before_tool` hook that changes the arguments after the guard has run is not covered: the guard checks the arguments it was given.
j. Missing config: without `AOS_GUARD_CFG` only the built-in denies apply (the stack, definition, daemon-table, daemon, `AOS_HOME` and `AOS_WRITE_DENY` entries and the rules); `deny_roots` is gone, and the tools that need a config rule (`shell`, `run_python`, `subagent`, `kernel_gate`, `agents_ctl`) are blocked. A config that is set but missing or broken is an error (exit 1). Likewise, an unset `AOS_DAEMON` or `AOS_HOME` drops the entries taken from it; the `proc-stack` and `definition-marker` rules still apply.
k. Recognition by names and marker files: mail boxes are judged by folder names (any path part named `requests`, `procs_requests` or `queue` not directly under the agent's own stack), so an ordinary folder with one of these names is refused as a `mailbox_send` box. The other way round, unusual daemon settings (no `procs_state.json`, a ctl mailbox placed outside the daemon folder, a kernel mailbox reached through a link) are not recognised as such by the mail rule. `proc-stack` and `definition-marker` go by layout and marker files; they back up the daemon table, and an ordinary folder named `.stack`, a stray `procs_state.json` or `interfaces.json` makes the folders around it unwritable.
l. If an agent's workspace lies inside its own stack, inside any proc's or daemon's stack, or inside a definition folder, every file-tool write is blocked. The default layout is the other way round.
m. Start-up environment: `_entry` runs with `#!/usr/bin/env python3`, without `-I`. Keep `PATH` and `PYTHONPATH` of the agent free of folders the agent can write, or a planted program or module could run in place of the guard's.
n. Only arguments: the guard sees the tool's name and arguments. A tool that writes somewhere not named in its arguments (its own stack, a fixed file) is not checked; that is why tools without a rule are blocked.
o. Not for kits with `move`, `remove` or `trash` yet: these tools act on a whole folder, and the guard checks the folder and the folders above it, not what is inside it (see "Write scope"). With them an agent could delete or move away a neighbour's stack, a definition or `.git` that lies inside a folder it may write, and change it at the new place. To do: also block these tools (and `move.to` / `copy.to` onto an existing folder) when a deny path lies under the folder, or the folder holds `.git`, `.stack`, `procs_state.json` or `interfaces.json` below it.
p. Cells cut once: `AOS_STACK` and the event's `stack` are cut by one cell level. An agent that runs as a tool in another agent's `<parent>/tools/X` denies `<parent>/tools/X`; `<parent>` itself is denied only through the daemon table or `proc-stack`.
q. Hook order: hooks run sorted by name, and a `before_tool` hook that runs after the guard can change the arguments it checked. Give the guard's entry a name that sorts last, or mount no other `before_tool` hook.

The guard never prints environment values, only variable names. The one exception is the folders a block message reports: `AOS_WS=...`, `AOS_WRITE_ALLOW=...` in "outside the folders you may write", the denied folder with its source in "inside a folder no agent may write", and the stack or definition folder found by a rule. Config errors name `AOS_GUARD_CFG`, not its path; the `agents_ctl` self-only message says "the last part of your AOS_STACK", not the name.

Fixed in review and kept in the tests: `uniq - OUT`, `uniq in -- -out`, `date -us`, `date MMDDhhmm`, `$IFS` splitting (an unquoted `$NAME` is always strict), the path, keep, stack, definition, daemon and unknown-tool cases of the first round, and of the second: a `box` on another tree, an unreadable daemon table, wrong argument types (exit 10, not 1), `keep: true` of `mailbox_send`, the event's `stack`.

## Tests

    env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

run from this folder (a clean environment: no `AOS_*` variables).
