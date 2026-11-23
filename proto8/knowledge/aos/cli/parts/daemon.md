# aos-daemon: the daemon itself

It looks after the procs in `daemon.json` and those added later through its `procs_requests` mailbox; an optional own `exec` body runs like aos-loop. Start a daemon from a definition whose `_entry` runs it:

```sh
unset AOS_CLOCK AOS_DAEMON AOS_STACK      # a set AOS_DAEMON makes a new root think it is a child
aos-exec --stack stacks/root defs         # defs/_entry: {"argv": ["aos-daemon", "--enable-logs", "daemon.json"]}
AOS_STACK=/tmp/st aos-daemon --max 10 daemon.json   # a short test: 10 rounds, then its procs sleep
```

Templates: `$AOS_HOME/templates/daemon-root` for the root of a tree; `$AOS_HOME/templates/daemon-sub` for a daemon under another one. Copy it, then attach the copy as a row of the daemon above: `aos-daemon-ctl -d <upper stack> add --auto-restart -n NAME -w WS <copy>`. Its README says how to attach agents under it and how to stop it.

Starting a root from an agent's shell (it carries `AOS_STACK`, `AOS_WS` and more): clear every `AOS_*` first, then set back only `AOS_HOME`. A leftover one makes the new root use the wrong folder.

Flags are the same as aos-loop (`--max`, `--interval-ms`, `--ctl`, `--state`, `--state-flux`, `--enable-counters`). It needs `AOS_STACK` (`StackMissing`). daemon.json takes `on_start` / `on_stop` like aos-loop (aos/cli/parts/loop.md): a failing on_start means the daemon does not start and none of its procs is started; a failing on_stop changes the exit code when it would have been 0. `on_before_run`, `on_after_run` and their `_if` keys are `CfgBad` in daemon.json. `--enable-logs` prints one JSON line per proc change. Control it with aos-daemon-ctl (`aos/cli/daemon.md`) and stop it with `aos-daemon-ctl shutdown`. Exit 0 of a proc removes its row; a known nonzero exit stays stopped; shutdown puts every live proc to sleep and the next start wakes them. Per proc, `stuck_after_cycles` / `stuck_after_ms` and `restart_on_stuck` handle a proc that does not answer its ctl window.

More flags: run `aos-daemon --help`.
