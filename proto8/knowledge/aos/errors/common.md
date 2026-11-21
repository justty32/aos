# Common error codes

The Codes you will meet most. More by kind: `aos/errors/common.md#/Codes about what you gave`, `aos/errors/common.md#/Codes from file work`, `aos/errors/common.md#/Codes from mailboxes`, `aos/errors/common.md#/Codes from external MCP tools`.

- `DaemonMissing`: `AOS_DAEMON` is unset or its directory does not exist. `DaemonFailed`: it exists but did not reply in time (busy, paused or down). `InstanceMissing`: no table row for you. `StateMissing`: the daemon's table file is not there (not started yet, or its state window is off). Features that need the daemon are unavailable for now: say so; try at most once more later.
- `AddRejected ... SlotMissing max_running N reached`: the kernel allows at most N running procs on its daemon's table. Remove a subagent or report.
- `AnswerMissing`: the agent you asked did not answer in time (or, when the line says `stopped on an error before answering`, its brain call failed and it stopped; the line carries that error: report it, do not just ask again). Check it with `subagent` (not yours: `agents_ctl`) op `state`: phase `stopped` with a `reason` means it crashed (fix or report); `running` or `stuck` means it is slow, ask again with a longer `timeout_s`. Phases: `aos/status.md`.
- `ToolExists`: use `replace: true` (`self_tools`) or `--replace` only if you mean to replace.
- `LlmKernelMissing`: an agent-fsm has no brain because `AOS_LLM_KERNEL` is unset or blank; it stops at once before sending, without cooldown, and keeps its request. Add it again with `envs {"AOS_LLM_KERNEL": "<llm kernel stack>"}` / `aos-agent ctl add --envs AOS_LLM_KERNEL=...`, or set it in the daemon's `.env`. `aos-llm` itself uses this code when the variable is unset/empty or its resolved path is not a folder (relative to `AOS_DAEMON`, otherwise the current directory); an agent-fsm with a configured but missing kernel folder still waits and retries.

# Codes about what you gave

- `ArgumentsBad`: the JSON you gave is not one object, misses a required key, or a value has the wrong type. A key the tool does not know is `ArgumentsBad` too: `unknown key foo (known: path, offset, max_lines)`; drop it. The reason says what is wrong; fix the call.
- `FlagUnknown`: a flag the command or tool does not know. `OpUnknown`: an `op` the tool does not have; its description lists the ops.
- `PointerBad`: a JSON Pointer is malformed. It starts with `/`; `""` is the whole document, which a write cannot replace.
- `CfgBad`: a settings file of the tool or of your definition is broken (not a JSON object, a wrong value). You cannot fix it with the call; report the file named in the reason.
- `ClockBad`: the clock file (`$AOS_CLOCK`) or a cycle number is not a valid integer. Waiting in cycles does not work until a human fixes it; report it.

# Codes from file work

- `WsMissing`: your workspace (`$AOS_WS`) is unset or not a folder. Tools do not fall back to the current folder. `StackMissing`: a tool that needs your stack (`$AOS_STACK`) has none. `ModuleMissing`: a tool's shared Python module was not found. All three are setup problems: report them.
- `ReadFailed`: the file or folder is there but could not be read (permissions, not a regular file, an I/O error); the reason names it. Check it with `stat`; do not retry the same path.
- `WriteFailed`, `CopyFailed`, `MoveFailed`, `RemoveFailed`: the system refused the change (permissions, disk full, something in the way). Look at what is there now before you retry.
- `LogFailed`: `shell` or `run_python` could not write its command log in your stack. `cannot prepare command log`: your command did not run. `cannot write command log`: it already ran, and what it did stays done.

# Codes from mailboxes

- `MailboxMissing`: the mailbox is not there: a `box` you gave does not exist, or the daemon you named has not started. Check the name or the box; do not create mailbox folders by hand.
- `MailboxBad`: the folder is not a mailbox (it needs `tmp/`, `new/` and `cur/`).
- `LetterBad`: a letter is broken (not valid `letter.json`). Report its name; read the next one.
- `StatusBad`: STATUS is not one of the six words (`aos/mailbox.md#/Mailbox rules`).
- `WriteFailed` from `mailbox_read` / `mailbox_send` with `keep` = a file name: that file cannot be written (its folder must exist). Read: the letter is still in your mailbox. Send: nothing was sent, unless the reason starts with `letter NAME was sent, but:`.

# Codes from external MCP tools

A tool whose description starts with `[MCP server NAME]` calls another program's server.

- `ServerFailed`: the server failed or timed out; retry once, then report.
- `ServerRejected`: the server refused the token (http 401/403); report, do not retry.
- `ServerBad`: the server broke the protocol; report.
- `CallFailed`: the tool itself said it failed; read its text above the error line.

All codes: `aos/cli/mcp_import.md#/Codes from external MCP tools`.
