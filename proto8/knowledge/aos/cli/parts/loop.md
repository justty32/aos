# aos-loop: run a body again and again

```sh
AOS_STACK=/tmp/st aos-loop --max 3 loop.json    # loop.json: {"exec": {"argv": ["sh", "-c", "echo run"]}}
AOS_STACK=/tmp/st aos-loop --interval-ms 100 loop2.json
```

Each run's exit code: 0 = run again, 10 = stop with exit 0, other = stop with that code (`aos-loop: error: RunFailed run 1: loop3.json#/exec failed with exit code 4`). It needs `AOS_STACK` for its ctl window (`StackMissing`). `aos-loop CONFIG -- ARGS` appends ARGS to every run's exec. Four optional points, each written like exec:

- `on_start` / `on_stop` run once (before the first run / when aos-loop is about to exit, not on SIGKILL); on_stop gets `AOS_LOOP_CODE`, `AOS_LOOP_SIGNAL` (signal number or empty) and `AOS_LOOP_CAUSE` (stop, sleep, remove, shutdown, stuck, signal, max, body_exit or error); both are limited by the top-level `on_timeout_ms` (default 5000, 0 = no limit).
- `on_before_run` / `on_after_run` run around each run of the body (no time limit unless the instruction sets `timeout_ms`). on_before_run gets `AOS_LOOP_RUNS`; exit 10 skips this run (not counted, no on_after_run, tried again after interval_ms). on_after_run gets `AOS_LOOP_RUNS`, `AOS_LOOP_RUN_CODE`, `AOS_LOOP_RUN_SIGNAL`, `AOS_LOOP_RUN_MS`; non-zero stops the loop only when the body exited 0 (else one warning).
- `on_before_run_if` / `on_after_run_if`: a file path; that point runs only while the file exists.
- A failing point (non-zero, timed out, cannot run) stops the loop with `PointFailed` and the point's code: on_start failing = the body never runs; on_stop failing changes the exit code only when it would have been 0.

A gate (optional `gate`, written like exec) asks before each run whether to run at all. aos-loop asks it when not paused and the time has come, before on_before_run.

- Exit 10 skips this run: no body, not counted (`max`, counter_runs), neither run point fires, and the state stays `waiting` without being rewritten. The next try is after interval_ms.
- Exit 0: aos-loop reads the ctl window again (a stop or pause sent meanwhile counts), then runs as usual.
- Any other code, a timeout or a gate that cannot start: one warning line (once per cause), and the body runs anyway.
- `gate_timeout_ms`: the gate's limit (default 1000, 0 = no limit; then SIGTERM, SIGKILL 1 s later). `gate_timeout_ms` without `gate` is `CfgBad`.
- No `gate` = nothing is asked.

The stock templates fill these points with `aos-hook fire` (aos/cli/offer_hooks.md). `--ctl`, `--state`, `--state-flux` choose the windows; `{"cmd": "pause"}`, resume and stop in the ctl window control it (that is what aos-daemon-ctl pause writes). `--enable-logs` prints one JSON line per run; `--enable-counters` writes counter_runs.txt next to the state window. Agents and daemon rows are loops started by a daemon; you seldom start one yourself.

More flags: run `aos-loop --help`.
