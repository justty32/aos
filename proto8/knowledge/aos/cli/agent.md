# Agent lifecycle

Use aos-agent ctl to attach agents and inspect or change their daemon state.

`ctl add` 工作區：`--ws DIR` ＞ 非空的 `$AOS_WS` ＞ 呼叫當下的 cwd；轉絕對路徑。選到的路徑不是資料夾＝`WsMissing`，不送信、不退回 cwd。

```sh
aos-agent ctl add --name bob --ws /work ../agents/bob
aos-agent ctl ls --json
aos-agent ctl state --target bob
aos-agent ctl stop --target bob
aos-agent ctl start --target bob
```

The definition must declare `aos-agent` in `interfaces.json`. `add` waits for the table and prints the stack. Optional `--stack DIR` chooses its stack. `--limits '{"mem_mb":512}'` replaces the definition's limits; `'{}'` means no limits. Repeatable `--envs NAME=VALUE` supplies environment variables when the agent starts.

`ls` prints NAME, STATE, WORKSPACE, QUEUED, REASON as TAB-separated columns. Empty means no rows. `state` (alias `status`) shows one agent's paths, queue, last answer, reason, limits and tool overlay.

`stop` finishes this round, keeps the stack and leaves `stopped`; use `start`. `sleep` sends SIGTERM now, keeps the stack and leaves `sleeping`; use `wake`, or restart the daemon. Wrong pairs give `PhaseBad`; use the command in its reason. An already reached state is a successful no-op in aos-agent.

`pause`/`resume` act between steps of a running loop. A long step can delay them. Stop and rm first close the screen; an answering screen can refuse with `SessionBad`. Sleep leaves the screen alone.

`aos-agent ctl where --target bob` prints its stack; `--ws` prints its workspace. Do not combine `--stack` and `--ws`.

`aos-agent ctl who` finds the owner of `$AOS_STACK`, including a nested tool stack. `--stack /path` chooses another stack; `--json` prints its details. This reads the daemon table, not parent directories.
