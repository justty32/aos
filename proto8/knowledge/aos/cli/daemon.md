# Daemon procs: direct control, bypassing the kernel

Use aos-daemon-ctl for arbitrary procs on one daemon; a sent letter is not proof that the requested change finished. To go through the kernel, use `aos-agent ctl` (`aos/cli/agent.md`).

# add: attach a proc

```sh
aos-daemon-ctl -d /srv/d add --name tick tick.json      # a loop config: runs again and again
aos-daemon-ctl -d /srv/d add --name job job.sh -- 3     # runs once; ARGS after --
aos-daemon-ctl -d /srv/d where --stack tick             # /srv/d/procs/tick
```

add prints a letter name. A loop config is an object with `exec` and no `argv`; other targets run once, and only those take ARGS after `--`. A definition folder runs its `_entry`; for an agent use `aos-agent ctl add`. Exit 0 of a run-once proc removes its row; a known nonzero exit stays `stopped` with a reason (`failed to start: exited within 3s of wake/start (code 3)`). `--auto-restart` restarts it on every exit, until 3 runs in a row exit within 3 s. `--def DEF` = definition folder kept on the table (default: the target); `--ws`, `--stack`, `--ws-json`, `--stack-json`, `--path-json`, `--limits` work as for `aos-agent ctl add`. `limits: {}` uses the daemon default. A nonempty `limits` replaces all numeric defaults: write every key you want; only a missing `user` comes from the default. Put any default key that requests must not remove in daemon.json `limits_max`; exceeding or omitting a capped key stops only that proc (`LimitBad`, no clamping). The default must name every capped key and stay within its cap. Rows may report `limit_hit` for a direct-child CPU/file-size signal and `limit_suspect` for exit 1 with `mem_mb` (a guess). A name already taken = `InstanceExists`; where or rm on a name not on the table = `ProcMissing`.

# stop, sleep, pause, rm

All procs can stop, start, sleep and wake. stop writes the proc's ctl window and waits for exit (no SIGTERM fallback): row `stopped`, back with `start`. sleep sends SIGTERM (SIGKILL after 10 s): row `sleeping`, back with `wake`. Wrong pairs give `PhaseBad` (sleep also takes `stopping` rows; pause/resume only running or stuck ones); already there = `NAME: already X`, exit 0. pause/resume write `{"cmd": "pause", "seq": N}` to the ctl window, print N and wait up to `--timeout-s` (default 5) for it to apply; a timeout warns and exits 0; the program decides whether to read it. rm detaches without asking; the stack stays. The ctl filename is a nonempty `ctl` in the parent-written loop config, else ctl.json. Sleeping rows wake at the next daemon start.

# Letters, waiting and the kernel

add/rm/stop/start/sleep/wake print a letter name and wait up to `--timeout-s` (default 3) for the daemon to claim it; `prune --apply` waits too but prints `NAME: removed`. A still-queued letter warns and exits 0. After the claim it briefly reads the daemon's reply: a refused letter is an error with the reason (`BodyBad`, else `CtlRejected`). A claim does not prove application: check `ls`. `--reply-to BOX` only sends; read the reply yourself (`applied: true|false`); it excludes `--timeout-s`.

aos-daemon-ctl names one daemon: it sends straight to that daemon's ctl mailbox and never reads `$AOS_KERNEL`; it works where you may write that mailbox. `aos-agent ctl` routes via `$AOS_KERNEL` and warns `routing via AOS_KERNEL=PATH`. A sleeping or stopped kernel is the designer's risk: wake it with `aos-daemon-ctl wake NAME` (stopped: `start`).

The daemon also answers a table question: a body `{"procs_state_path": true}` and a `reply_to` gets `{"applied": true, "procs_state_path": "<absolute path of its procs_state.json>"}` (`null` when its procs_state window is off), changing nothing; another value = `BodyBad`. aos-daemon-ctl never sends it (`ls`, `where` read the files). `aos-agent ctl ls`/`who`/`where`/`state` send it to `$AOS_KERNEL` before reading the table, wait 3 s (`--timeout-s`) and fail with `KernelFailed` instead of reading `$AOS_DAEMON` (`aos/kernel.md#/Where to send requests`).

# ls, ping, poke

```sh
aos-daemon-ctl -d /srv/d ls
aos-daemon-ctl -d /srv/d ping        # replied in 108 ms
aos-daemon-ctl -d /srv/d poke --all  # run a full round now
```

```text
_clock	running	1082359	-	-	-
# daemon: running (pid 1082357)
# root daemon (no supervisor)
```

ls columns (TAB): NAME PHASE PID CODE WS REASON. The last two lines start with `# `: whether this daemon runs, and what its supervisor thinks; skip them in parsers. `ls -j` prints one object (`running`: daemon alive). A daemon with a body (llm kernel, kernel station) whose last round failed says so on the `# daemon:` line (`; its body failed last round (code N; the reason is in the daemon's stderr)`; `ls -j`: `body_code`): letters to that kernel are not being handled. ls and where only read files: no proof of liveness. ping waits for a reply (`DaemonFailed` on timeout). poke is a doorbell: `--ctl` (default), `--mail` or `--all`; write ctl or send a letter first. Other codes: `CtlMissing` (ctl window off), `StateMissing`, `StateBad`, `PokeFailed`. More flags: run `aos-daemon-ctl --help`.

# shutdown: stop the whole daemon

```sh
aos-daemon-ctl -d stacks/root shutdown
# daemon at /.../stacks/root stopped (ctl seq 1); 2 procs asleep
```

Every running proc sleeps and stays on the table; starting the daemon again wakes them. It waits up to `--timeout-s` (default 15); still running = `StillRunning`: do not commit or copy the stacks yet; run it again. A stop already in progress stays stopped, a sleep in progress becomes sleeping, an rm in progress is removed; if kill -9 interrupts shutdown, the next start reaches the same result.

# prune: check rows and remove old ones

```sh
aos-daemon-ctl -d /srv/d prune
aos-daemon-ctl -d /srv/d prune --older-than 7d
aos-daemon-ctl -d /srv/d prune --older-than 7d --apply
```

`prune` prints each suspicious row as `NAME: PHASE: PROBLEM` (missing stacks, bad ctl files, stopped reasons); findings alone exit 0.

`--older-than` (a positive integer plus `s`, `m`, `h` or `d`) selects only stopped/sleeping rows whose latest stack change (the stack folder and its direct files) is older; rows without a stack are never selected. Preview lines are `NAME: would remove (last change ISO_TIME)`. `--apply` requires `--older-than`, uses the same letter path as `rm` and prints `NAME: removed`; stacks and workspaces stay.

# sweep: one sweeper round now

```sh
aos-daemon-ctl -d /srv/d sweep --dry-run
aos-daemon-ctl -d /srv/d sweep --purge --dry-run
```

sweep runs the same code as the `_sweeper` row (`aos/cli/sweeper.md`) inside this command, so it works when that row is paused or missing. `--purge` deletes every stderr archive of this daemon (asks on a terminal; `-y` skips). Archives are deleted by age only with `--retention-days N`; `--min-bytes` and `--stop-grace-s` tune the round. `--purge` does not go with these three (`ArgumentsBad`). Another sweeper busy longer than `--timeout-s` (default 30) = `SweepBusy`. `-j` prints the round as JSON.

# Optional cgroup v2

Set daemon.json cgroup to off (default), auto (warn and fall back if probing fails) or on (CfgBad if it fails); start it yourself in a delegated scope: systemd-run --user --scope --collect -p Delegate=yes -- aos-daemon daemon.json (launch.json wrap is not implemented). After taking the stack lock, the daemon moves into base/daemon and enables memory/pids on base and base/procs. limits mem_total_mb sets memory.max with memory.swap.max=0 when available; procs_total sets pids.max for the proc and descendants, including threads. Both take positive integers and limits_max caps; without cgroup they warn once and appear in limits_ignored. Each enabled row reports its absolute cgroup path; re-launch recreates the empty group and resets events. On direct-child exit, cpu_s/file_mb hits win, then oom_kill gives limit_hit mem, then pids max gives procs; a hit clears limit_suspect. Adopted running rows do not read events. Exit-zero rows are still removed; end logs gain no hit/suspect fields. Graceful stop is unchanged; cgroup.kill also collects remaining descendants (setsid ones too) on exit or after the 10-second kill grace. Procs running under your own uid can rewrite cgroupfs: for them these limits contain accidents, not tampering. `--limits` and the kernel station's default/max tables accept both; aos-sandbox does not.

# Running a proc as a subuid (limits.user sub:N)

`limits: {"user": "sub:5"}` runs that proc as subuid 5 of the daemon's user, without root: real uid = the first /etc/subuid start of that user + N - 1 (start 100000 gives 100004). N is 1 to 60000. Usually the kernel fills it from its `users` table; you do not choose it. All such procs of one daemon share one primary group: daemon.json `group` (60001 to 65536, default 60001; the daemon's state.json shows it); supplementary groups are dropped. `procs` in such a proc counts only that proc's own processes and threads (two procs with the same sub:N count separately); the whole account stays under the daemon's own process limit.

Before the start the daemon makes the proc's stack 0700 with ACL entries for that uid and for the daemon's user, so the user can still read and edit what the proc writes. The proc gets only PATH, LANG, LC_ALL, LC_CTYPE, TZ, TERM, PYTHONDONTWRITEBYTECODE, PYTHONIOENCODING and AOS_* from the environment, HOME=/nonexistent, and git safe.directory set to its ws.

Needs newuidmap/newgidmap (package uidmap) and every parent folder of the stack, the daemon's cwd and the ws searchable by that uid. Errors stop only that proc with a reason: `LimitBad user sub:5: newuidmap not found on PATH (install the uidmap package)`, `LimitBad user sub:5: cannot reach /home/me: Permission denied` (a home folder that others cannot enter), `LimitBad user sub:5: setgroups: ...`. Mailboxes and shared folders are not opened for it: use aos-share. `groups` in limits is not accepted yet.
