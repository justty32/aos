# Errors and retries

Read the program name, error code and reason before choosing whether to retry.

Errors use stderr: `PROGRAM: error: Code reason`, usually exit 1. `PROGRAM: warning: text` is a reminder and may exit 0. stdout contains results. Exit 10 means "nothing there" (no letter, no lock, no reply yet). A child program can report its own error; do not treat it as a parsing error in aos-agent. See also general errors (`aos/errors.md`).

# Codes you will meet

- `ArgumentsBad`, `FlagUnknown`, `CommandUnknown`: fix the call. Follow its usage or the suggested level of `--help`.
- `CommandMissing`: put the named dependency (such as aos-exec, aos-json, aos-post, bwrap) on PATH.
- `TargetMissing`: give `--target`, set `$AOS_AGENT`, or run it inside the agent's stack (aos/cli/flags.md `target`).
- `InstanceMissing` (daemon-ctl: `ProcMissing`): the name is not on the table. Check `ctl ls`.
- `InterfaceMissing`, `ToolsMissing`, `LlmMissing`, `HooksMissing`, `SystemMissing`: the definition lacks the required interface or file. Fix the definition or choose a supported action.
- `PhaseBad`: use start for stopped, wake for sleeping; follow the reason.
- `SessionBad`: the screen is answering; wait before close, stop or rm.
- `TrustMissing`: claude on the eca screen waits at its trust-this-folder prompt; nothing was typed. A person must choose: attach (`aos-agent open`) or run `claude` in that folder once. Do not answer the prompt for them.
- `AddRejected`/`CtlRejected`: read the daemon or kernel's code and reason. Fix that cause before sending again.
- Other codes: `InterfaceBad`, `LlmBad`, `SystemBad`, `ToolsBad` (a declared file or the tools list is unreadable or malformed); `ScreenBad` (the screen entry exited with an error); `StateMissing` (not a daemon stack: no `procs_state.json`); `QuestionUnknown` (listen: nothing was asked yet); `KeyMissing` (llm rm: key not changed); `HistoryBad`, `MessageBad` (history file unreadable, set JSON not one object); `WriteFailed` (a stack file cannot be written); `PostFailed` (say: aos-post failed). See `aos/errors.md`.
- `StackMissing`: `AOS_STACK` is not set; the parts (aos-loop, aos-fsm, aos-daemon) need it.

# Timeouts and retries

ctl add/rm/start/stop/sleep/wake wait for replies; `--timeout-s S` defaults to 30. `DaemonMissing` means no daemon was found (no `--daemon` or `$AOS_DAEMON`, and for aos-agent no daemon two folders up from an agent's stack in the current folder; aos-daemon-ctl still tries `./.stack`), its directory does not exist, or no daemon runs there; nothing was sent. `DaemonFailed` means the daemon runs, but no reply arrived within the timeout. `WaitFailed` means the expected result did not arrive; a kernel may be non-running, or a reply arrived but the table did not reach the result.

A timed-out letter is withdrawn if still unclaimed; the reason says `letter withdrawn, it will not be applied` or `could not withdraw it; it may still be applied`. Do not send duplicates in a row. Check `aos-daemon-ctl ping`, `ctl ls` and `ctl state`; retry later only after checking the result.

`AnswerMissing` means no answer was available or the wait timed out. It does not prove the agent stopped, unless it says `stopped on an error before answering`: then the agent's brain call failed and the agent stopped on it, and the line carries that error (for example `EndpointFailed HTTP 400 ...`); fix that cause instead of waiting. A failed brain call the agent retries by itself is a warning while waiting and is added at the end of a timeout line (`X's last brain call failed: ...`). Inspect state, then listen again rather than blindly repeating say. If the letter name is known, `listen --letter NAME`; the error line names the letter and its last state.

`LetterDropped` (ask, chat, listen --letter) means the agent dropped that letter and will never answer it: it was not a valid message, a `before_queue` hook blocked it, or an eca agent's CLI failed after taking it. The reason is in the line. Say it again for a new answer.
