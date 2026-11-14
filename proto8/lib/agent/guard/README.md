# guard: before_tool guard for file, shell, mail and control tools

> **Status: under review. Do not mount this hook to restrict agents yet.** An independent review found ways around some checks; fixes are in progress. It is not wired into any shipped definition or kit.

`guard` is a before_tool hook handler (python3, stdlib only). It reads the tool call on stdin (`{"name": ..., "arguments": {...}}`) and answers with its exit code:

| exit | meaning |
|---|---|
| 0 | allowed (nothing on stdout) |
| 10 | blocked: one line `[aos] guard: blocked: ...` on stdout, which the agent sees as the tool result |
| 1 | error: one line `guard: error: CODE reason` on stderr (`CfgMissing`, `CfgBad`, `ArgumentsBad`, `WsMissing`); mounted with `on_error: "stop"` the call does not run |

It checks: file-tool paths against the write scope (below) and `.git`; shell commands (`shell_deny` regexes, with the relaxed check below); `subagent` ops; `clock_register` boxes; `mailbox_send` boxes and names; `kernel_gate` ops; `agents_ctl` (ring the bell: stop yourself only).

Derived from fsm-guard (commit 313ce20ec): same checks and the same tests (they hold the bypasses found in three review rounds), with neutral messages and one source for the write scope.

Files: `_entry` (the hook handler; `_entry --scope` prints the write scope), `guard.py` (the checks, importable), `scope.py` (the write scope, importable; `python3 scope.py` prints it), `tests/`.

## Mount it

hooks.json of the definition (or a stack copy written by `self_hook`):

    "guard": {"event": "before_tool",
              "condition": ["write", "edit", "copy", "move", "mkdir", "trash", "remove", "json_set", "json_add", "json_del", "json_multi_set", "mailbox_send"],
              "handler": {"$env": "AOS_HOME", "$path": "/lib/agent/guard"},
              "on_error": "stop", "timeout_ms": 10000}

List only the tools the kit gives: add `shell`, `run_python`, `clock_register`, `subagent`, `kernel_gate`, `agents_ctl` to `condition` only if the agent has them (see "Known limits" h for the last two). `on_error` must be `"stop"`: a broken config is an error (exit 1), and with `"continue"` an error would let the call through. Remove the guard = drop the hook entry.

The hook runs with the agent's environment, except that `AOS_STACK` is the hook's own cell `<stack>/hooks/guard` and `AOS_CD` is this folder. Put `AOS_GUARD_CFG`, `AOS_WRITE_ALLOW` and `AOS_WRITE_DENY` in the agent's environment (the definition's `.env`, or `aos-agent ctl add --envs`).

## Write scope (scope.py)

One source, read the same way by the guard and by anything else (`python3 scope.py` or `_entry --scope`; in Python `scope.write_scope(env=None)`):

    {"allow": [{"path": "/abs/ws", "from": "AOS_WS"}, {"path": "/abs/b", "from": "AOS_WRITE_ALLOW"}],
     "deny":  [{"path": "/abs/stack", "from": "AOS_STACK"}, {"path": "/abs/guard", "from": "AOS_CD"},
               {"path": "/abs/def", "from": "definition"}, {"path": "/abs/s", "from": "AOS_WRITE_DENY"},
               {"path": "/abs/x", "from": "guard.json"}]}

Exit 0 with that object on stdout (one line); exit 1 with `scope: error: CODE reason` on stderr. Every path is absolute and resolved. A file-tool path may be written when it is at or under an `allow` path and not at or under a `deny` path; deny is checked first.

- allow: `realpath($AOS_WS)` always, plus each entry of `AOS_WRITE_ALLOW` (separated by `:`, the OS path separator).
- deny, none of which the config can lift:
  - `AOS_STACK`: the agent's own stack (a hook or tool cell `<stack>/hooks/<name>` or `<stack>/tools/<name>` counts as `<stack>`);
  - `AOS_CD`: when set (in a hook: this folder);
  - `definition`: the agent's definition folder, when it can be found reliably: the `def` of the row in `$AOS_DAEMON/procs_state.json` whose `stack` holds `AOS_STACK` (the deepest such row, as `aos-agent ctl who` does; shards `{"$ref": [...]}` are joined; relative values count from the daemon folder). Skipped (no entry) when `AOS_DAEMON` is unset or not absolute, when `AOS_KERNEL` is set (then the table can only be asked for by letter, which a hook does not do), or when the table, the row or its `def` cannot be read. The stack itself records no definition path that can be trusted (the `$override` pointer in a stack's `tools.json` exists only after `self_tools` and goes stale when a stack is copied or `set-def` runs);
  - `AOS_WRITE_DENY`: each entry, separated like `AOS_WRITE_ALLOW`;
  - `guard.json`: the config's `deny_roots`.
- Every path is read the same way (entries above, file-tool paths, `deny_roots`, `clock_boxes`, `mail_deny`, the `subagent` def and ws, a mail `box`): `~` or `~/...` is the home folder (`HOME`; `~user` is not expanded), then a relative path counts from `AOS_WS`, then symlinks and `..` are resolved. A link inside the workspace that points outside it is judged by where it points.
- Block messages name the rule: `... is outside the folders you may write (AOS_WS=/a, AOS_WRITE_ALLOW=/b) ...`, `... is inside a folder no agent may write (/s, from AOS_STACK) ...`.
- A config with a `write_roots` key is refused (`CfgBad`, exit 1, for every tool call): move those folders to `AOS_WRITE_ALLOW`.

## Config (guard.json)

The file named by `AOS_GUARD_CFG`. Unset or empty = no config (the defaults below). Set but not a file = `CfgMissing`; not JSON or not an object = `CfgBad`.

Keys: `deny_roots` (list), `deny_parts` (default `[".git"]`), `shell_deny` (regex list, `re.search` over the whole command), `subagent` (`ops`, `def`, `ws`, `name` regex; no `name` = any name), `clock_boxes` (list), `mail_deny` (list), `mail_allow_to` (regex), `mail_foreign_queue` (`"deny"` or `"allow"`; any other value = `CfgBad` for every tool call), `kernel_gate` (`ops`), `agents_ctl` (`ops`, `self_only`, `max_timeout_s`).

Defaults: no `shell_deny` key = `shell` and `run_python` are blocked (an empty list `[]` is a rule: nothing denied); no `subagent`, `kernel_gate` or `agents_ctl` rule = that tool is blocked; no `clock_boxes` = `clock_register` may only wake the agent itself; no `mail_allow_to` = any name; no `mail_foreign_queue` = `"deny"`.

## Mail (`mailbox_send`)

- `box` given: blocked when its real path is at or under
  - a daemon ctl mailbox: a daemon stack is a folder with `procs_state.json`; its ctl mailbox is the folder named by that file's `procs_requests` key (default `procs_requests`). Any path part named `procs_requests` also counts, marker or not;
  - a kernel mailbox: any path part named `requests` (`<station stack>/requests`, `$AOS_LLM_KERNEL/requests`, `<stack>/hooks/kernel_gate/requests`, `<stack>/hooks/<gate>/requests`), or `$AOS_KERNEL` / `$AOS_LLM_KERNEL` when set;
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

The guard is only an entry in the agent's hooks.json. An agent with `self_hook` can drop or replace it in its stack copy; one with `self_tools` can add a tool that does. A kit that relies on the guard must not give its agents `self_hook` or `self_tools`. (The guard denies file-tool writes to the agent's own stack, so the stack copy of hooks.json cannot be changed with the file tools.)

## Known limits

a. Not a security boundary. The sandbox (aos-sandbox / bwrap) is the write boundary; the guard only stops slips. The deny list and the mail rule apply to tool calls, not to what a shell command writes (a shell sandbox can read the same list with `_entry --scope`).
b. Regex gaps (handled only as "not plain read-only", not blocked): the strict `shell_deny` regex is whatever the config says; an example list like the one in the tests misses `git --no-optional-locks commit`, `git -c a=b commit`, `{rm,-f} x`, `r\<newline>m x`, `"rm" x`, `r''m x`, `$RM x`, `ls | xargs rm` (no blank after rm). The tests check that these are not plain read-only, not that they are blocked.
c. Shell environment trust: handled. The relaxed check is skipped when `PATH` has a relative or empty entry, or `BASH_ENV`, `ENV`, `RIPGREP_CONFIG_PATH` or a `BASH_FUNC_*` variable is set (see above); the block message names the variable, not its value (`PATH has a relative or empty entry`). Other variables that change a program's behaviour (for example `LD_PRELOAD`) are not looked at; the sandbox bounds them.
d. Tool versions: the whitelist was reviewed against GNU coreutils 9, ripgrep 14, GNU sed 4.9, jq 1.7 and procps-ng. BSD tools or a newer rg may give options other meanings; `RG_LONG` is a fixed list and must be updated if rg adds options that run programs.
e. Deliberately allowed, not blocked: `cd` (changes the directory for later commands); `sort` writes temp files in `$TMPDIR` on large input; `df --sync` calls sync(2); `tail -f` hangs (until the tool's timeout). Reading is not limited: `cat` / `jq` can read any file the tool may read, secrets included; that is not the guard's job.
f. Shell tool parameters other than `command`: only `command` (shell) and `code` (run_python) are looked at; the shell tool has only `command` and `timeout_s` today. If it gains `cwd`, `env` or similar, the guard must look at them. `run_python` is always strict (its code is not shell).
g. TOCTOU: a path is resolved (realpath) when it is checked, so a symlink can be swapped between the check and the write; the sandbox is the backstop.
h. `kernel_gate` and `agents_ctl` are only checked when hooks.json's `condition` lists them; listing them without a rule in the config blocks them completely. The same holds for `subagent`, and for `shell` / `run_python` without `shell_deny`.
i. Mail boxes are judged by folder names: any path part named `requests`, `procs_requests` or `queue` (a `queue` not directly under the agent's own stack) is treated as a kernel, control or queue mailbox, so an ordinary folder with one of these names is refused as a `mailbox_send` box.
j. If an agent's workspace lies inside its own stack, every file-tool write is blocked: the stack is denied and deny is checked before allow. The default layout is the other way round (the stack is not inside the workspace).

The guard never prints environment values, only variable names. The one exception is the folders a block message reports as write roots: `AOS_WS=...`, `AOS_WRITE_ALLOW=...` in "outside the folders you may write", and the denied folder with its source in "inside a folder no agent may write". Config errors name `AOS_GUARD_CFG`, not its path; the `agents_ctl` self-only message says "the last part of your AOS_STACK", not the name.

Fixed in review and kept in the tests: `uniq - OUT`, `uniq in -- -out`, `date -us`, `date MMDDhhmm`, `$IFS` splitting (an unquoted `$NAME` is always strict).

## Tests

    env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

run from this folder (a clean environment: no `AOS_*` variables).
