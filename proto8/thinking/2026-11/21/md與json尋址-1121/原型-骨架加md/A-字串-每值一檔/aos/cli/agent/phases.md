# Stop, sleep, pause

```sh
aos-agent ctl stop bob     # finish this round; stopped; back with start
aos-agent ctl start bob
aos-agent ctl sleep bob    # SIGTERM now; sleeping; back with wake (or a daemon restart)
aos-agent ctl wake bob
aos-agent ctl pause bob    # hold between steps; back with resume
aos-agent ctl resume bob
```

Wrong pairs give `PhaseBad` (`ann is stopped; use start (wake only wakes sleeping ones)`). An already reached state is a successful no-op (`already asleep (sleeping)`). `stop`, `pause`, `sleep` and `rm` take `--no-wait` (return once the daemon has the request; this is how an agent stops itself). A long step can delay pause/resume. Rm and set-def first close the screen; an answering screen can refuse with `SessionBad`. Stop and sleep leave the screen alone: an eca closes it from its after_stop hook `screen_linger_stop` after cli.json `screen_close_after_s` seconds (default 600, 0 = at once; aos/cli/eca.json#/screen_linger), unless it starts again first; `aos-agent close` closes it now. With `$AOS_KERNEL` set and no `--daemon`, add, start, stop, sleep, wake and rm without `--purge` go through the kernel and read only the letter's reply: the name check (`InstanceExists`), the table read and the screen close described here do not happen, and start, stop, sleep, wake and rm print `... accepted for NAME`. Removing: `aos/cli/safety.json#/rm`. The whole daemon: `aos/cli/daemon.json#/shutdown`.
