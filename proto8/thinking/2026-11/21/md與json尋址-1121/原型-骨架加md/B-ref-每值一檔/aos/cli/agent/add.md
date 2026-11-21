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
- `--limits '{"mem_mb":512}'` replaces the definition's limits (the aos-sandbox keys); `'{}'` = none. Repeatable `--envs NAME=VALUE`. Never put a secret in `--envs`: the value is stored in plain text in `procs/<name>/exec.json` (mode 666 minus umask, usually 644) and shows on the command line; an MCP token goes in the server file's `env_file` (see the eca template's cli.json `mcp_servers`).
- `--parent P` (who asked for it, stored as `AOS_PARENT_STACK`) and `--notify-box B` (where its notices go, `AOS_NOTIFY_BOX`) are stored in its envs like `--envs`; `--kit KIT` lays a kit over a new definition (aos/kits.json).
- `--on-queued ok`: exit 0 when the letter is still queued after `--timeout-s`.
- Another definition for an agent already on the table: `aos-agent ctl set-def NAME DEF` stops it (after this round), detaches it (its stack stays) and attaches it again with DEF on the same stack. Its stack (history, queue, mailbox), workspace, limits and auto_restart stay. The table shows DEF at once and keeps it across a daemon restart. A running one starts again with DEF; a stopped one stays stopped and a sleeping one stays asleep. Letters sent to it while it is detached are refused. Not for an agent attached with `--envs` (or `--parent` / `--notify-box`), and not for an agent on itself (`ArgumentsBad`).
- Renaming: `aos-agent ctl rm OLD` (the stack stays), then `aos-agent ctl add -n NEW -s <old stack> [-w <ws>] [--auto-restart] <definition>`. The stack folder is not moved (its path keeps the old name; that is fine). Letters sent to OLD meanwhile are refused. One attached with `--envs` needs its `--envs` again.
