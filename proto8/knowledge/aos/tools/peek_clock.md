# Tool peek_clock

Look at the daemon clock: the current cycle number and how long one cycle is. No arguments. Changes nothing.

Use it to know how far the clock is, for example before you give `timeout_cycles` or `every` to another tool. For the time of day use `peek_now_time`.

```json
{}
```
-> `{"cycle": 42, "interval_ms": 1000}`

- `cycle`: the number in the clock file `$AOS_CLOCK`. The root daemon adds 1 per tick. An empty clock file counts as 0. It does not move while the clock is paused or the tree sleeps.
- `interval_ms`: about how many ms one cycle is (`$AOS_CLOCK_INTERVAL`, default 1000).
- Cycle numbers compare only inside one tree. More about time: `aos/world.md` (section Time).

Errors: `aos/tools/peek_clock.md#/peek_clock: errors`.

# peek_clock: errors

- `ClockMissing`: you have no clock. `AOS_CLOCK` is not set (you are not under a daemon tree with a clock), or its file is not there yet (the clock is off or has not ticked). Do not guess a cycle: use `peek_now_time` for the time of day, or say so.
- `ClockBad`: the clock file does not hold a number, or `AOS_CLOCK_INTERVAL` is not a positive integer. A human must fix it; report.
- `ArgumentsBad`: give `{}` (no keys). See `aos/errors/common.md#/Codes about what you gave`.
