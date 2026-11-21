# Hooks on one agent

Use aos-agent hook to run a program when something happens to one agent. It writes only that agent's own copy `<stack>/hookeds.json`; the definition's `hookeds.json` stays as it is. The definition's `interfaces.json` must name the list at its top level, `"hookeds": "hookeds.json"`, otherwise `HooksMissing` (its `"hooks"` key names the hook point declarations, only for reading).

```sh
aos-agent hook -t bob                       # = ls: NAME TAB EVENT TAB HANDLER
aos-agent hook -t bob ls -l                 # also CONDITION TIMEOUT_MS FROM, and hooks set to null
aos-agent hook -t bob ls --json
aos-agent hook -t bob get guard
aos-agent hook -t bob add --event before_tool --condition agents_ctl --timeout-ms 5000 hooks/guard   # exit 10 blocks the call
aos-agent hook -t bob add --event brain_failed -n ping --path-json '{"$env": "AOS_HOME", "$path": "/lib/x"}'
aos-agent hook -t bob add --event on_clock --every-ms 600000 -n check hooks/check   # every 10 minutes of clock cycles; --every-cycles N, --clock PROC_OR_PATH, --config JSON
aos-agent hook -t bob rm guard              # a definition hook is set to null; an own hook is deleted
aos-agent hook -t bob reset -y              # delete the agent's own list, back to the definition's
```

- Flags of add: `--event` (required; not checked against any declaration), `-n/--name`, `--condition` (only for these tool names / error codes; repeatable), `--timeout-ms N` (default 60000; 0 = no limit), `--replace`, `--path-json`, and for on_clock `--every-cycles` / `--every-ms`, `--clock`, `--config`.
- A failing hook (exit code not 0 / 10, too slow, cannot start, bad stdout): on before_queue and before_tool the event stops (the agent stops with HookFailed); on the other events it is one warning line; on the loop events (after_start, after_stop, before_run, after_run) the loop stops.
- The name defaults to the file or folder name; with `--path-json`, `--name` is required. `NameBad`: empty, has `/`, starts with `.`, or is `description`.
- A relative path is from the current directory; missing = `PathMissing`.
- `HookExists`: add `--replace`. `HookMissing`: no hook of that name. `HooksBad`: the list is broken.
- Events include after_start / after_stop (the loop starts / is about to exit), before_run / after_run (around each run of the loop body; exit 10 of a before_run hook skips that run; only when the definition's loop.json wires them, else add prints a warning: recompile and restart), before_compact / after_compact (around agent-fsm's /compact, and an eca with claude through its compact_hook; a failing hook there is only a warning; aos/me/compact.md) and on_clock (needs --every-cycles or --every-ms; nothing enters the history); on_clock runs once right after add, start or wake, then every N, and the event has `first`.
- Eca screen lifecycle: the stock screen_linger_start / screen_linger_stop hooks cancel / schedule delayed screen closure (cli.json screen_close_after_s, default 600 seconds, 0 immediate). Set both to null to disable it. See `aos/cli/eca.md#/Delayed screen closure`.
- Writing the handler program (stdin, `$AOS_STACK` = the hook's own folder `<stack>/hookeds/NAME/`, a JSON entry instead of chmod): `aos/me/self_hook.md#/Writing the hook program`; a mailbox-check example: `aos/mailbox.md#/The mail_notify hook`.
- Events and the answer protocol are the same as for the agent's own tool: `aos/me/self_hook.md`.