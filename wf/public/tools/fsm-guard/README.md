# fsm-guard: before_tool guard for agent-fsm teams (lead / worker)

`guard` is a before_tool hook handler (python3, stdlib only). It reads the tool call on stdin (`{"name": ..., "arguments": {...}}`) and exits 0 (allowed) or 10 with `[aos] guard: blocked: ...` on stdout. It checks: file-tool paths (inside `write_roots`, never a `.git` part), shell commands (`shell_deny` regexes, with the relaxed check below), `subagent` ops, `clock_register` boxes, `kernel_gate` ops, `agents_ctl` (ring the bell: stop yourself only). The kernel_gate / agents_ctl branches only matter if hooks.json lists those tools.

## Mount it on a definition
Put `guard` in `defs/shared/`; in each definition a 4-line wrapper `guard` (aos-exec runs a symlink by its real path, so pass the config explicitly):

    #!/bin/sh
    # guard wrapper: pass this definition's guard.json to the shared guard.
    d=$(dirname "$0")
    AOS_GUARD_CFG="$d/guard.json" exec python3 "$d/../shared/guard"

hooks.json: `{"hooks": {"guard": {"event": "before_tool", "condition": ["write", "edit", "copy", "move", "mkdir", "trash", "json_set", "json_add", "json_del", "json_multi_set", "shell", "clock_register"], "handler": "guard", "on_error": "stop", "timeout_ms": 10000}}}` (add `subagent`, `kernel_gate`, `agents_ctl` where used). Remove = drop the hook entry. The hook needs `AOS_WS` (set by aos).

guard.json keys: `write_roots` (list), `deny_parts` (default `[".git"]`), `shell_deny` (regex list, `re.search` over the whole command), `subagent` (`ops`, `def`, `ws`, `name` regex), `clock_boxes` (list), `kernel_gate` (`ops`), `agents_ctl` (`ops`, `self_only`, `max_timeout_s`). A missing rule for subagent / kernel_gate / agents_ctl = that tool is blocked.

## Relaxed shell check (tool `shell` only; `run_python` is always strict)
A command skips `shell_deny` only if it is "plain read-only"; anything else gets the old whole-text regex check (its block message then says "strict check ..."). Plain read-only = all of:
- Quoting is tracked per character. Single quotes: literal. Double quotes: no `\`, no backtick, `$` only as `$NAME`.
- Unquoted: words of `A-Za-z0-9_./,:=@%+*?!~^-` and quotes (an unquoted `$NAME` is strict: bash splits it on IFS and globs it; write `"$NAME"`); separators `;` `|` `&&` `||` newline; the only redirections are the words `2>/dev/null`, `>/dev/null`, `2>&1`. Anything else (`\`, backtick, `#`, `{}`, `[]`, `()`, `<`, `>`, single `&`, `$(`, `${`, `$[`, `$'`, `$1`, `$_`, non-ASCII, CR, NUL or another control character anywhere, an unclosed quote, an empty command) = strict.
- Every simple command's first word is unquoted, matches `^[A-Za-z0-9_-]+$` and is one of: cat head tail wc grep egrep fgrep rg ls pwd cd echo printf true false test pgrep ps stat basename dirname realpath readlink du df cmp md5sum sha1sum sha256sum nl cut uniq tr column comm jq date id whoami uname which sort sed.
- An argument with an unquoted `*` or `?` must start with a literal other than `-` (a glob could expand to a planted file name like `--pre=sh`).
- rg, sed, sort, printf: no `$` in any argument. rg: every `--option` is in a fixed safe list (no `--pre`, `--hostname-bin`, `--search-zip`, ...), no short option cluster with `z`. sed: exactly `sed -n SCRIPT FILE...`, SCRIPT = `N p`, `N,M p`, `N,$ p` or `$p` (no spaces), no FILE starts with `-`. sort: options only clusters of `unrVhf`. printf: first argument does not start with `-` (`-v` assigns). uniq: no `$` or glob, no `-` or `--` argument, at most one argument not starting with `-` (`uniq IN OUT` writes OUT). date: no `$` or glob, every argument starts with `-` or `+`, no short option cluster with `s`, no `--s...` (`-s`, `-us`, `--set`, `MMDDhhmm` set the clock).

Examples that pass: `rg -n 'rm accepted' x`, `pgrep -u "$USER" -af aos-daemon`, `sed -n '1,20p' f && rg --files . | rg 'aos-x'`. Not plain (strict): anything with git, xargs, find, interpreters, `$(...)`, `> file`.

## Known limits
- The sandbox (aos-sandbox / bwrap, `shell-boxed`) is the real write boundary; this guard only stops slips. The strict regex is unchanged: `git --no-optional-locks commit` and `git -c a=b commit` are not caught by the worker pattern; `{rm,-f} x`, `r\<newline>m x`, `ls | xargs rm` (no blank after rm) are not caught either.
- Allowed, by choice: `cd` changes the directory for the rest of the line; `sort` may write temp files in `$TMPDIR` on large input; `df --sync` calls sync(2).
- The relaxed check trusts the shell's environment (also `RIPGREP_CONFIG_PATH`): a PATH with relative entries, exported bash functions or BASH_ENV in the tool's env could change what `cat` runs.

## Tests
    cd wf/public/tools/fsm-guard && python3 -m unittest discover -s tests -v
(run with a clean environment: no AOS_* variables).

## Author
ok-astra (claude subagent, reviewed by ok-astra), 2026-11-14. Based on the gpt team's shared-k guard; relaxed check designed by ok-astra after two Argon review rounds of the design and a third of this code.
