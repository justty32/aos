# Agent lifecycle

Use aos-agent ctl to attach agents and inspect or change their daemon state. `aos-agent ctl --help` prints a table of the three stop pairs (stop/start, sleep/wake, pause/resume) and rm.

# ctl add: attach one agent

```sh
aos-agent -d stacks/root ctl add --auto-restart -w . defs/ann
# /.../stacks/root/procs/ann        (it prints the stack)
aos-agent ctl add --name bob --ws /work ../agents/bob
```

XXX is the definition folder (not a folder = `PathMissing`). Its `interfaces.json` may declare `aos-agent` (for example an `entry`); without that declaration the folder itself is started. The same name = `InstanceExists`; a refusing daemon or kernel = `AddRejected`.

- Workspace: `--ws DIR`, nonempty `$AOS_WS`, then the current directory; not a directory = `WsMissing`, nothing is sent.
- `--stack DIR` chooses its stack (default `<daemon stack>/procs/<name>/`).
- `--ws-json`, `--stack-json`, `--path-json` store a directive such as `'{"$env": "PROJ"}'`; it is resolved again on every start.
- `--dotenv-override`: start it with `aos-exec --dotenv-override`, so its `.env` may override names already set (stored in the row; that hop only).
- `--auto-restart`: the daemon restarts it whenever it exits; only for agents that stay up.
- `--limits '{"mem_mb":512}'` replaces the definition's limits (the aos-sandbox keys); `'{}'` = none. `mem_mb` caps address space, not memory in use: for Node, Chromium or a JVM use `mem_total_mb`. Repeatable `--envs NAME=VALUE`. Never put a secret in `--envs`: the value is stored in plain text in `procs/<name>/exec.json` (mode 666 minus umask, usually 644) and shows on the command line; an MCP token goes in the server file's `env_file` (see the eca template's cli.json `mcp_servers`).
- `--parent P` (who asked for it, stored as `AOS_PARENT_STACK`) and `--notify-box B` (where its notices go, `AOS_NOTIFY_BOX`) are stored in its envs like `--envs`; `--kit KIT` lays a kit over a new definition (aos/kits.md).
- `--on-queued ok`: exit 0 when the letter is still queued after `--timeout-s`.
- Another definition for an agent already on the table: `aos-agent ctl set-def NAME DEF` stops it (after this round), detaches it (its stack stays) and attaches it again with DEF on the same stack. Its stack (history, queue, mailbox), workspace, limits and auto_restart stay. The table shows DEF at once and keeps it across a daemon restart. A running one starts again with DEF; a stopped one stays stopped and a sleeping one stays asleep. Letters sent to it while it is detached are refused. Not for an agent attached with `--envs` (or `--parent` / `--notify-box`), and not for an agent on itself (`ArgumentsBad`).
- Renaming: `aos-agent ctl rm OLD` (the stack stays), then `aos-agent ctl add -n NEW -s <old stack> [-w <ws>] [--auto-restart] <definition>`. The stack folder is not moved (its path keeps the old name; that is fine). Letters sent to OLD meanwhile are refused. One attached with `--envs` needs its `--envs` again.

# ctl ls and ctl state

```sh
aos-agent ctl ls                 # NAME STATE WORKSPACE QUEUED REASON (TAB-separated)
aos-agent ctl ls -l              # + QUEUE RESTARTS COOLDOWN LAST ERROR
aos-agent ctl state -t bob       # one line per part
aos-agent ctl state -t bob tools history   # only these parts, in full
```

An empty table prints nothing. `-j` prints JSON. `state` (alias `status`) has the parts who, state, tools, llm, system, hooks, history, mailbox, subagents, resources, time; give part names for detail, or `all`. `state tools` lists every tool and ends with `own: N listed, M set to null (...)` when the agent changed its tools.

The whole tree, with the tables of procs that are daemons themselves: `aos-comm -d <root stack> board ls --deep [-j]` (at most 5 levels and 500 procs, then `truncated`). Its columns are the notice board's (NAME MODE DOING WAITING BACK), with no phase and no pid.

# Stop, sleep, pause

```sh
aos-agent ctl stop bob     # finish this round; stopped; back with start
aos-agent ctl start bob
aos-agent ctl sleep bob    # SIGTERM now; sleeping; back with wake (or a daemon restart)
aos-agent ctl wake bob
aos-agent ctl pause bob    # hold between steps; back with resume
aos-agent ctl resume bob
```

Wrong pairs give `PhaseBad` (`ann is stopped; use start (wake only wakes sleeping ones)`). An already reached state is a successful no-op (`already asleep (sleeping)`). `stop`, `pause`, `sleep` and `rm` take `--no-wait` (return once the daemon has the request; this is how an agent stops itself). A long step can delay pause/resume. Rm and set-def first close the screen; an answering screen can refuse with `SessionBad`. Stop and sleep leave the screen alone: an eca closes it from its after_stop hook `screen_linger_stop` after cli.json `screen_close_after_s` seconds (default 600, 0 = at once; `aos/cli/eca.md#/Delayed screen closure`), unless it starts again first; `aos-agent close` closes it now. With `$AOS_KERNEL` set and no `--daemon`, add, start, stop, sleep, wake and rm without `--purge` go through the kernel and read only the letter's reply: the name check (`InstanceExists`), the table read and the screen close described here do not happen, and start, stop, sleep, wake and rm print `... accepted for NAME`. Removing: `aos/cli/safety.md#/Removing an agent`. The whole daemon: `aos/cli/daemon.md#/shutdown: stop the whole daemon`.

# Finding agents and stacks

```sh
aos-agent ctl where bob          # its stack
aos-agent ctl where --ws bob     # its workspace
aos-agent ctl who                # the owner of $AOS_STACK, also from a nested tool stack
aos-agent ctl who --stack /path/to/stack --json
# {"name": "ann", "stack": "...", "ws": "...", "def": "...", "daemon": "...", "parent": null, "notify_box": null}
```

`parent` and `notify_box` are what the requester wrote at add time (`--parent`, `--notify-box`), not proof.

Do not combine `--stack` and `--ws` in where. who reads the daemon table, not parent directories. With $AOS_KERNEL set (and no --daemon), who, ls, where and state first send {"procs_state_path": true} to $AOS_KERNEL and read the table file named in the reply; no reply within --timeout-s (default 3) = KernelFailed, with no fallback to $AOS_DAEMON. --daemon D reads that daemon directly.
