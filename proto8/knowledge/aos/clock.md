Timers: clock letters to your queue (tool clock_register: every N cycles, once after N cycles, once at a wall-clock time, or cron), or a program on a clock that adds nothing to your conversation (an on_clock hook). Which to choose: `aos/clock.md#/Doing something on a timer: which way`.

# Wake me every N cycles

Call clock_register with op add, a name, every and text; leave out box:
{"op": "add", "name": "check-inbox", "every": 10, "text": "Check data/ for new files."}
Every 10 cycles you get a user message "[aos] clock: cycle 30. Check data/ for new files.". Remove it with {"op": "rm", "name": "check-inbox"}; list with {"op": "ls"}.
To wake another agent, give box = its STACK/queue. Shell: aos-clock-register add --every N --box BOX NAME TEXT.
Once, or at a wall-clock time: `aos/clock.md#/Wake me once, at a time, or on a schedule`.
The register belongs to the clock in $AOS_CLOCK; give daemon D (shell -d D) to use the clock D/clock instead.

# Wake me once, at a time, or on a schedule

clock_register add takes exactly one of every, after, at, cron:

- `after`: once, N cycles from now: {"op": "add", "name": "recheck", "after": 30, "text": "Re-run the tests."}
- `at`: once at a wall-clock time, local time of the machine: `"21:30"` (today; tomorrow if already past), `"2026-11-14 09:00"`, or from now `"+10m"`, `"+2h"`, `"+1d"` (s, m, h, d): {"op": "add", "name": "call", "at": "21:30", "text": "Send the report to ann."}
- `cron`: repeating wall-clock times, 5 fields `minute hour day-of-month month day-of-week`, local time: `"0 9 * * 1"` = Mondays 09:00, `"*/15 * * * *"` = every 15 minutes, `"30 8 * * 1-5"` = weekdays 08:30. Fields take `*`, `N`, `A-B`, `*/S`, `A-B/S` and comma lists; day of week 0-7 (0 and 7 = Sunday); when both day of month and day of week are set, either one matches. No names (`mon`, `jan`) and no `@daily`.

`after` and `at` entries remove themselves after their letter; `every` and `cron` stay until you `rm` them. The add result says when it fires (`once at 2026-11-13 21:30`, `cron 0 9 * * 1, next 2026-11-16 09:00`); `ls` shows each entry's WHEN. The local time now: peek_now_time {"local": true} (`2026-11-13T21:05:00+08:00 Friday`).

A wall-clock letter says when it was due: `[aos] clock: cycle 812, due 2026-11-13 21:30. Send the report to ann.`, with `(late by 2h 5m)` when it comes more than a minute late.

Timing:

- Entries are checked each time the root clock moves one cycle (about once a second): a wall-clock letter comes at most one cycle late.
- `after` counts cycles: while the tree sleeps or the clock is paused, no cycles pass and the wait does not run out.
- `at` and `cron` count wall time: one that came due while the tree slept is sent once at the first cycle after waking; a `cron` entry missed many times is sent once, not once per miss, and its next time is counted from then.
- A due letter that cannot be sent is one warning line from the clock and is not retried: a one-time entry is removed anyway, a cron entry moves to its next time (the same as `every`).
- Errors: `ArgumentsBad` (none or two of every/after/at/cron; after not a positive integer; at or cron not understood; at already past; a cron that never fires), `ClockBad` (the clock file is unreadable), and the ones in `aos/clock.md#/Clock letters: rules`.

# Clock letters: rules

- It fires when the cycle number divides by every (10, 20, 30 for every 10), not counted from when you added it.
- Anyone who can write the register can add or remove any entry. Remove your entry when you no longer need it; the clock itself only removes entries whose box folder is gone (checked every 100 cycles by default).
- A letter that cannot be sent is only a warning line from the clock; the clock keeps going.
- While you sleep, letters wait in your queue; you get them all when you wake.
- Errors: `EntryExists` (the name is taken: pick another, or `"replace": true`), `EntryMissing` (no entry with that name: `ls` first), `ClockMissing` (no clock: you are not under a daemon tree with one; or give `daemon`), `RegisterBad` (the register file next to the clock cannot be read: a human must fix it), `WriteFailed` (the register cannot be written). Without `box`: `DaemonMissing` / `InstanceMissing` = you are not on a daemon table, so you have no queue to wake; give `box`.
- A screen a person opens (`aos-agent open`) gets `AOS_CLOCK` as your loop has it. A screen opened before this was fixed, or before your loop ran once, took it from that person's shell, where it can be missing: `peek_clock` and `clock_register` then answer `ClockMissing` although the tree has a clock. Have the screen closed and opened again. `on_clock` hooks are not affected: they run in your loop, not in the screen.

# A timer that does not enter your conversation

clock_register letters arrive in your queue, so each one becomes a message. To only run a program on a clock, use a hook instead:
self_hook {"op": "add", "event": "on_clock", "every_ms": 600000, "path": "hooks/check"}
It runs hooks/check when the clock moved 10 minutes' worth of cycles since the last run (checked at the start of each of your steps; once, however many were missed; never while you sleep; it also runs once right after you start, wake up or restart). The program gets clock, cycle, interval_ms, first, last_cycle, missed on stdin. Nothing reaches you unless it sends a letter to your queue (aos-post send STACK/queue). Your definition may have a timer hook (every 5 minutes, does nothing) to replace, and a mail_notify hook (every minute; `aos/mailbox.md#/Hearing about new letters`). How to write the program: `aos/me/self_hook.md#/Writing the hook program`.
every_ms is turned into whole clock cycles, rounded up: the real gap can be longer than written, not shorter. After a wake the event has first true and missed 0; it does not say how long you slept (a handler that catches up by itself: `aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`). Without a clock (AOS_CLOCK not set and no clock key) the hook never runs: your log gets one warning line, and wall time is not used instead.

# Doing something on a timer: which way

Three ways, told apart by what enters your conversation (history):

1. Clock letter (`clock_register`): a fixed text arrives in your queue every N cycles, once (`after`, `at`), or on a wall-clock schedule (`cron`; `aos/clock.md#/Wake me once, at a time, or on a schedule`). Each one is a message in your history and one brain turn, even when there is nothing to do. Use it when you must think every time.
2. `on_clock` hook (`self_hook`): a program runs every N cycles or ms. Nothing enters your history; no brain turn is spent. Use it when a program alone can do the job (copy files, write a log).
3. `on_clock` hook that writes to your queue only when there is news: the program checks something and sends one letter to your queue only then. History grows only then. Example: the stock `mail_notify` hook, on by default (`aos/mailbox.md#/Hearing about new letters`). Another example: a job at a wall time that first checks whether there is work (every day at 09:00, every 3 days): `aos/me/self_hook.md#/A job at a wall time (every day at 09:00)`. Just a reminder at a wall time, no check: `clock_register` with `at` or `cron` is simpler.

On an eca body every brain turn costs money: prefer 2 or 3. A message already in your history can be removed with `self_history`. How to write the program: `aos/me/self_hook.md#/Writing the hook program`.
