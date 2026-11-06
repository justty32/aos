# Daemon procs and routing

Use aos-daemon-ctl for arbitrary procs; a sent letter is not proof that the requested change finished.

```sh
aos-daemon-ctl --daemon /srv/d add --name clock --stack /tmp/clock ../lib/base/clock
aos-daemon-ctl --daemon /srv/d where --stack clock
aos-daemon-ctl --daemon /srv/d ping --timeout-s 3
```

add detects a loop config by its final structure. Other targets run once as exec procs. Extra argv are allowed only for exec types, after `XXX -- ARGS...`. exec types cannot stop, sleep, pause or resume (`CtlMissing`). stop/start and sleep/wake keep stacks; rm detaches and also keeps the stack.

add/rm/stop/start/sleep/wake print a letter name and wait up to `--timeout-s` (default 3) for claim. A still-queued letter gives a warning and exit 0. Claim does not prove application. `--reply-to BOX` sends only; you must read the reply (`applied: true|false`). It excludes `--timeout-s`.

With `$AOS_KERNEL`, these six actions and ping route through the judge. Before sending, stderr says `aos-daemon-ctl: warning: routing via AOS_KERNEL=PATH (the judge decides and forwards)`. The table still comes from the chosen daemon. Check both locations before sending.

`aos-agent` also warns when routing via AOS_KERNEL. Actions on the kernel itself (start/stop/sleep/wake/rm) go directly to the daemon so a sleeping kernel can be woken.

ls/where only read files. `ls --json` prints one object. Text ls ends with a `# ` supervisor comment; skip that line in parsers. It does not prove liveness; ping asks for a reply.

pause/resume write the proc's ctl window directly, bypassing AOS_KERNEL. They wait for application (default 5 s); timeout warns and exits 0. No state window means no wait.
