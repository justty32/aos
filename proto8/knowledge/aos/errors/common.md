# Common error codes

The Codes you will meet most, and what each one means for you.

- `DaemonMissing`: `AOS_DAEMON` is unset or its directory does not exist. `DaemonFailed`: the daemon is configured and its directory exists, but no reply arrived within the timeout (busy, paused or down). `InstanceMissing`: no table row for you. Features that need the daemon are unavailable for now: say so, do not retry in a row; you may try once more later.
- `AddRejected ... SlotMissing max_running N reached`: the judge allows at most N running procs on its daemon's table (the _sweeper row counts too). Remove a child or report.
- `AnswerMissing`: the agent you asked did not answer in time. Check its row with `agents` `{"op": "ls"}`: phase `stopped` with a `reason` means it crashed (fix or report); `running` means it is slow, ask again with a longer `timeout_s`. Phases: node `status`.
- `ToolExists`: use `replace: true` (`self_tools`) or `--replace` only if you mean to replace.
- `LlmKernelMissing`: the brain service is not configured; a human must start it.

11-06 note: `ArgumentsBad` covers malformed or non-object stdin JSON, missing required keys, and schema type mismatches. `FlagUnknown` means an unrecognized flag; extra stdin keys are ignored. `enum` values are shown in help but checked by the tool itself (an unknown operation remains `OpUnknown`). `WsMissing` means the workspace is absent or invalid; lib tools do not default it to the current directory. `StackMissing` means a tool that needs execution state has no stack; `ModuleMissing` means its shared Python module could not be found. See [J1 implementation](../../../thinking/2026-11/05/json-argv/08-J1實作結果.md) and [J2 implementation](../../../thinking/2026-11/05/json-argv/09-J2實作結果.md).
