# Error codes

What each Code ending means, what to do, and the Codes you will meet most.

The Code is the word right after `error: `. Its ending:

| ending | meaning | what to do |
|---|---|---|
| `...Bad` | something you gave is malformed or not allowed (`ArgumentsBad`, `PathBad`, `RequestBad`, `NameBad`) | fix the argument and retry once |
| `...Missing` | something that should exist does not (`PathMissing`, `FileMissing`, `WsMissing`, `DaemonMissing`, `AnswerMissing`, `BudgetMissing`) | create it, wait for it, or report that it is not there. Do not retry blindly |
| `...Unknown` | a name was not found in a list (`OpUnknown`, `FlagUnknown`, `CommandUnknown`, `ChildUnknown`, `EndpointUnknown`, `ToolUnknown`) | list what exists, then use a name from the list |
| `...Failed` | an action was attempted and failed (`WriteFailed`, `LaunchFailed`, `EndpointFailed`, `CommandFailed`) | usually environmental; retry once, then report |
| `...Rejected` | a gatekeeper said no (`AddRejected`, `CtlRejected`) | this is a decision. Adapt (remove something, ask for less) or report. Never loop |
| `...Internal` | a bug in the program | report it with the full line |

Codes you will meet most:

- `DaemonMissing`: no daemon found, or the daemon did not reply (busy, paused or down). `InstanceMissing`: no table row for you. Features that need the daemon are unavailable for now: say so, do not retry in a row; you may try once more later.
- `AddRejected ... SlotMissing max_running N reached`: the judge allows at most N running agents. Remove a child or report.
- `AnswerMissing`: the agent you asked did not answer in time. Check its row with `agents` `{"op": "ls"}`: phase `stopped` with a `reason` means it crashed (fix or report); `running` means it is slow, ask again with a longer `timeout_s`. Phases: node `status`.
- `ToolExists`: use `override: true` only if you mean to replace.
- `LlmKernelMissing`: the brain service is not configured; a human must start it.
