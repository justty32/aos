# Daemon procs: direct control, bypassing the judge

Use aos-daemon-ctl for arbitrary procs; a sent letter is not proof that the requested change finished.

```sh
aos-daemon-ctl --daemon /srv/d add --name clock --stack /tmp/clock ../lib/base/clock
aos-daemon-ctl --daemon /srv/d where --stack clock
aos-daemon-ctl --daemon /srv/d ping --timeout-s 3
```

add detects a loop config by its final structure. Other targets run once as exec procs. Extra argv are allowed only for exec types, after `XXX -- ARGS...`. exec types cannot stop, sleep, pause or resume (`CtlMissing`). stop/start and sleep/wake keep stacks; rm detaches and also keeps the stack.

add/rm/stop/start/sleep/wake print a letter name and wait up to `--timeout-s` (default 3) for claim. A still-queued letter gives a warning and exit 0. Claim does not prove application. `--reply-to BOX` sends only; you must read the reply (`applied: true|false`). It excludes `--timeout-s`.

aos-daemon-ctl always sends straight to the chosen daemon's ctl mailbox; it never reads `$AOS_KERNEL` and bypasses any judge. To go through the judge, use `aos-agent ctl`, which routes via `$AOS_KERNEL` and warns `routing via AOS_KERNEL=PATH`. A sleeping or stopped judge is the system designer's risk: wake it by hand with `aos-daemon-ctl wake NAME` (stopped: `start`).

ls/where only read files. `ls --json` prints one object. Text ls ends with a `# ` supervisor comment; skip that line in parsers. It does not prove liveness; ping asks for a reply.

pause/resume write the proc's ctl window directly. They wait for application (default 5 s); timeout warns and exits 0. No state window means no wait.
