# Daemon procs: direct control, bypassing the judge

Use aos-daemon-ctl for arbitrary procs; a sent letter is not proof that the requested change finished.

```sh
aos-daemon-ctl --daemon /srv/d add --name clock --stack /tmp/clock ../lib/base/clock
aos-daemon-ctl --daemon /srv/d where --stack clock
aos-daemon-ctl --daemon /srv/d ping --timeout-s 3
```

add detects a loop config by its final structure. Other targets run once as exec procs. Extra argv are allowed only for exec types, after `XXX -- ARGS...`. All procs can stop, start, sleep and wake regardless of launch syntax. Stop writes the public ctl window and waits for exit without SIGTERM fallback; sleep uses SIGTERM and keeps a sleeping row. The ctl filename comes from a nonempty ctl in the parent-written loop config, otherwise ctl.json. Pause/resume use the same path; the program decides whether to read it. Known nonzero exits stay stopped with a reason; exit 0 leaves the table (auto_restart still governs restarts). On daemon shutdown, running rows become sleeping; a stop already in progress stays stopped, a sleep in progress becomes sleeping, and an rm in progress is removed. If kill -9 interrupts shutdown, startup follows the table's `stop_mode` and reaches the same result. Sleeping rows wake next startup. stop/start and sleep/wake keep stacks; rm detaches and also keeps the stack.

add/rm/stop/start/sleep/wake print a letter name and wait up to `--timeout-s` (default 3) for claim. A still-queued letter gives a warning and exit 0. Claim does not prove application. `--reply-to BOX` sends only; you must read the reply (`applied: true|false`). It excludes `--timeout-s`.

aos-daemon-ctl always sends straight to the chosen daemon's ctl mailbox; it never reads `$AOS_KERNEL` and bypasses any judge. To go through the judge, use `aos-agent ctl`, which routes via `$AOS_KERNEL` and warns `routing via AOS_KERNEL=PATH`. A sleeping or stopped judge is the system designer's risk: wake it by hand with `aos-daemon-ctl wake NAME` (stopped: `start`).

ls/where only read files. `ls --json` prints one object. Text ls ends with a `# ` supervisor comment; skip that line in parsers. It does not prove liveness; ping asks for a reply.

pause/resume write the proc's ctl window directly. They wait for application (default 5 s); timeout warns and exits 0. No state window means no wait.

## Prune: check rows and preview old entries

```sh
aos-daemon-ctl --daemon /srv/d prune
aos-daemon-ctl --daemon /srv/d prune --older-than 7d
aos-daemon-ctl --daemon /srv/d prune --older-than 7d --apply
```

`prune` prints each suspicious row as `NAME: PHASE: PROBLEM`: missing stacks, ctl files that are not JSON objects, stale running/stopping process identities, and stopped reasons. Pending stopped/sleeping rows with both pid and code null do not need a stack yet. Findings alone exit 0.

`--older-than` selects only stopped/sleeping rows whose latest stack mtime is strictly older than the threshold. This is the newest mtime of the stack directory itself and its direct files; subdirectories are not scanned. Rows without a stack are never selected. Durations are a positive integer plus `s`, `m`, `h` or `d` (for example `7d`). Preview lines are `NAME: would remove (last change ISO_TIME)`.

`--apply` requires `--older-than`. It uses the same removal-letter path as `rm` and prints `NAME: removed`; all stack/workspace files stay. This asks the daemon to detach the proc. The default wait checks only whether the letter was claimed, not whether the removal was applied; `--reply-to BOX` sends only so you can read the applied reply yourself.
