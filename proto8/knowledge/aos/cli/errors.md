# Errors and retries

Read the program name, error code and reason before choosing whether to retry.

Errors use stderr: `PROGRAM: error: Code reason`, usually exit 1. `PROGRAM: warning: text` is a reminder and may exit 0. stdout contains results. A child program can report its own error; do not treat it as a parsing error in aos-agent. See also [general errors](../errors/README.md).

- `ArgumentsBad`, `FlagUnknown`, `CommandUnknown`: fix the call. Follow its usage or the suggested level of `--help`.
- `CommandMissing`: put the named dependency (such as aos-exec, aos-json or aos-post) on PATH.
- `TargetMissing`: give `--target` or set `$AOS_AGENT`.
- `InstanceMissing` (daemon-ctl: `ProcMissing`): the name is not on the table. Check `ctl ls`.
- `InterfaceMissing`, `ToolsMissing`, `LlmMissing`: the definition lacks the required interface or file. Fix the definition or choose a supported action.
- `PhaseBad`: use start for stopped, wake for sleeping; follow the reason.
- `SessionBad`: the screen is answering; wait before close, stop or rm.
- `AddRejected`/`CtlRejected`: read the daemon or judge's code and reason. Fix that cause before sending again.

ctl add/rm/start/stop/sleep/wake wait for replies; `--timeout-s S` defaults to 30. `DaemonMissing` can mean no daemon was found OR no reply arrived. `WaitFailed` means the expected result did not arrive; a kernel may be non-running, or a reply arrived but the table did not reach the result.

A timed-out letter stays queued and may still be applied later. Do not send duplicates in a row. Check `aos-daemon-ctl ping`, `ctl ls` and `ctl state`; retry later only after checking the result.

`AnswerMissing` means no answer was available or the wait timed out. It does not prove the agent stopped. Inspect state, then listen again rather than blindly repeating say.
