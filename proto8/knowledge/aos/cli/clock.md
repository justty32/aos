# The clock and its letters

The root daemon's `_clock` row moves a clock file every second; a register next to it sends letters every N cycles, once, or at wall-clock times. Agents use tools `peek_clock` and `clock_register` instead (`aos/clock.md`).

# aos-clock: one cycle forward

```sh
aos-clock clock && cat clock    # 1   (a missing or empty FILE counts as 0)
aos-clock clock && cat clock    # 2
```

It prints nothing. You rarely run it by hand: the root daemon runs `aos-clock $AOS_DAEMON/clock` as its `_clock` row. After each cycle it sends the letters of `FILE_register.json` (see `register`). A letter that cannot be sent is one warning line (`aos-clock: warning: clock register entry w2: cannot send to .../nobox: MailboxMissing ...`); the clock still moves and exits 0. A FILE that is not a number or cannot be read = `ClockBad`, FILE untouched. Other codes: `WriteFailed`, `FlagUnknown`, `LaunchFailed` (cannot start aos-clock-register). No FILE = `ArgumentsBad`. `aos-clock register ARGS...` is `aos-clock-register ARGS...` (a clock file really named register: write `./register`).

# aos-clock-register: letters on a schedule

```sh
Q=stacks/root/procs/ann/queue
aos-clock-register -d stacks/root add --every 10 --box $Q ann-wake "Check data/ for new files."  # cycles 10, 20, 30 ...
aos-clock-register -d stacks/root add --after 5 --box $Q ann-once "Look again."  # once, 5 cycles from now
aos-clock-register -d stacks/root add --at +15m --box $Q ann-standup "Post the status letter."  # once, wall clock
aos-clock-register -d stacks/root add --cron "0 9 * * 1" --box $Q ann-monday "Weekly review."  # Mondays 09:00
aos-clock-register -d stacks/root ls        # ann-wake  10  procs/ann/queue  Check data/ for new files.
aos-clock-register -d stacks/root rm ann-wake
```

The clock: `-c FILE` > `-d D` (D/clock) > `$AOS_CLOCK`; none = `ClockMissing`, both = `ArgumentsBad`; long names `--clock`, `--daemon`. The register is `CLOCK_register.json` next to it (`ls -j` prints `{file, check_every, letters}`). add takes exactly one schedule (`ArgumentsBad` otherwise): `--every N` fires when the new cycle number divides by N and stays; `--after N` fires once, N cycles from now; `--at WHEN` fires once at a local time (`HH:MM`, `YYYY-MM-DD HH:MM` or `+10m`; a past time = `ArgumentsBad`); `--cron EXPR` repeats by a 5-field cron expression in local time. Once-entries remove themselves. Wall-clock entries are checked when the clock moves, so at most one cycle late; one missed while the tree slept is sent once after waking. The ls schedule column is `10`, `cycle N`, `at TIME` or `cron EXPR next TIME`. The letter arrives as a user message `[aos] clock: cycle N. TEXT` (wall-clock ones: `cycle N, due TIME. TEXT`). The same name = `EntryExists` (`--replace`); an unknown name in rm = `EntryMissing`. A box that is not a mailbox yet is a warning, added anyway. Every `check_every` cycles (default 100) entries whose box folder is gone are removed. Other codes: `RegisterBad` (broken register file), `WriteFailed`, `CommandUnknown`, `ClockBad`. More flags: run `aos-clock-register --help`.
