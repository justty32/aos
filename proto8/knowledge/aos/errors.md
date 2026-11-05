# Reading an error

Every aos program fails the same way: one line `program: Code reason`. The Code's ending tells you the kind of problem.

The line: `self_tools: PathBad /etc/x is an absolute path outside the tool library ...`. First word = who failed. Second word = the Code. The rest = a human-readable reason, often with a hint after a semicolon.

The Code's ending:

| ending | meaning | what to do |
|---|---|---|
| `...Bad` | something you gave is malformed or not allowed (`ArgumentsBad`, `PathBad`, `RequestBad`, `NameBad`) | fix the argument and retry once |
| `...Missing` | something that should exist does not (`PathMissing`, `FileMissing`, `WsMissing`, `DaemonMissing`, `AnswerMissing`, `BudgetMissing`) | create it, wait for it, or report that it is not there. Do not retry blindly |
| `...Unknown` | a name was not found in a list (`OpUnknown`, `EndpointUnknown`, `ChildUnknown`, `ToolUnknown`) | list what exists, then use a name from the list |
| `...Failed` | an action was attempted and failed (`WriteFailed`, `LaunchFailed`, `EndpointFailed`, `CommandFailed`) | usually environmental; retry once, then report |
| `...Rejected` | a gatekeeper said no (`AddRejected`, `CtlRejected`) | this is a decision. Adapt (remove something, ask for less) or report. Never loop |
| `...Internal` | a bug in the program | report it with the full line |

Codes you will meet most:

- `DaemonMissing`, `InstanceMissing`: no daemon or no table row for you; features that need the daemon are unavailable.
- `AddRejected ... SlotMissing max_running N reached`: the judge allows at most N running agents. Remove a child or report.
- `AnswerMissing`: the agent you asked did not answer in time. Check its row with `agents` `{"op": "ls"}`: phase `stopped` with a `reason` means it crashed (fix or report); `running` means it is slow, ask again with a longer `timeout_s`. Phases are explained in node `status`.
- `ToolExists`: use `override: true` only if you mean to replace.
- `LlmKernelMissing`: the brain service is not configured; a human must start it.
- Exit code in a tool result (`... exit 1`): the tool itself ran but the command inside failed; read its output, it is the answer.

A tool that answers with text but no error line succeeded, even if the text says "no", "none" or "(none)".
