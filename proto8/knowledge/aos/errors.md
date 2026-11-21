# Reading an error

How to read a failed call: the `error:` line, `warning:` lines, and exit codes.

A failed aos program prints one error line: `program: error: Code reason`.

`self_tools: error: ToolExists math is already listed in your tools (add replace: true to replace it)`

- First word = who failed (a program, a tool, or an agent name).
- The word right after `error: ` = the Code. Its ending tells the kind of problem: see `aos/errors.md#/Error codes`; the most common Codes: `aos/errors/common.md`; Codes explained on other pages (`PhaseBad`, `BudgetMissing` ...): `aos/errors.md#/Where a Code is explained`.
- The rest = the reason, for humans. A usage hint comes last: `(usage: ...)`.

A tool you call prints the error line on stdout too, and exits 1. A failed or timed-out tool result also shows the last 2048 bytes of its stderr. A tool that runs past its time limit (`timeout_ms` in its `_metainfo.json`; 0 = no limit) is stopped. A flag that cannot be parsed adds `(see NAME --help)` to the reason; `NAME --help` lists the tool's parameters and the error codes it declares.

`program: warning: sentence` is not an error. The call worked; the line only tells you something. Never retry because of a warning.

Exit codes, and the `[exit code N]` line of `shell` / `run_python`: `aos/errors.md#/Exit codes`.

A tool that answers with text but no error line succeeded, even if the text says "no", "none" or "(none)".

# Error codes

What each Code ending means and what to do.

The Code is the word right after `error: `. Its ending:

| ending | meaning | what to do |
|---|---|---|
| `...Bad` | something you gave is malformed or not allowed (`ArgumentsBad`, `PathBad`, `RequestBad`, `NameBad`) | fix the argument and retry once |
| `...Missing` | something that should exist does not (`PathMissing`, `FileMissing`, `WsMissing`, `DaemonMissing`, `AnswerMissing`, `BudgetMissing`) | create it, wait for it, or report that it is not there. Do not retry blindly |
| `...Unknown` | a name was not found in a list (`OpUnknown`, `FlagUnknown`, `CommandUnknown`, `SubagentUnknown`, `EndpointUnknown`, `ToolUnknown`) | list what exists, then use a name from the list |
| `...Failed` | an action was attempted and failed (`WriteFailed`, `LaunchFailed`, `EndpointFailed`, `CommandFailed`) | usually environmental; retry once, then report |
| `...Exists` | something with that name is already there (`ToolExists`, `InstanceExists`, `DefExists`, `LetterExists`) | do not overwrite. Pick another name; use `replace` (`--replace`) only if you mean to replace |
| `...Rejected` | a gatekeeper said no (`AddRejected`, `CtlRejected`) | this is a decision. Adapt (remove something, ask for less) or report. Never loop |
| `...Internal` | a bug in the program | report it with the full line |

These are the common endings, not all of them: some Codes end otherwise (`DepthExceeded`, `SubagentQueued`, `ChildrenExist`). Read the reason after the Code; the tool's own node says what to do.

The Codes you will meet most: `aos/errors/common.md`. A Code that is explained on another page (`PhaseBad`, `BudgetMissing`, `InstanceExists` ...): `aos/errors.md#/Where a Code is explained`.

# Exit codes

- `0`: done.
- `10`: done, and the answer is "nothing" (no letter, no lock, no reply yet, a check found problems). Not an error: act on the "nothing".
- `130`: stopped by Ctrl-C. `128+N`: killed by signal N (`143` = TERM, often a timeout). `141`: a human command whose output pipe closed early (for example `| head`); not a failure.
- other non-zero: failed. If its stderr has `itsname: error:`, the program itself failed; if not, the code came from something it ran.

Tools that run your command (`shell`, `run_python`) end stdout with `[exit code N]`: the exit code of your command, not of the tool. Non-zero there means your command failed; read its output, it is the answer.

# Where a Code is explained

Codes you often meet that this page and `aos/errors/common.md` do not explain. Read the place named.

| Code | explained in |
|---|---|
| `PhaseBad` | `aos/agents.md#/Any agent on the table: agents_ctl`; also `aos/cli/agent.md#/Stop, sleep, pause`, `aos/cli/errors.md#/Codes you will meet` |
| `InstanceExists` | `aos/agents.md#/Any agent on the table: agents_ctl` |
| `HoldRefused` | `aos/kernel.md#/Being a kernel yourself: kernel_gate`; inside a `CtlRejected` line: `aos/agents.md#/Any agent on the table: agents_ctl` |
| `SubagentSlotMissing` | `aos/agents/subagent.md#/subagent: quota and errors` |
| `BudgetMissing` | `aos/brain.md#/Priority and budgets` |
| `RequestBad` (brain request) | `aos/brain.md#/Asking the brain` |
| `DeadlineBad` | `aos/brain.md#/Brain error codes` |
| `KeyMissing` | `aos/me/self_llm.md` (op `rm`); `aos/cli/errors.md#/Codes you will meet` |
| `SchemaBad` | `aos/user_zone.md#/How to send` |
| `SpecBad` | `aos/tools/json_get.md#/JSON tools: the path` |
| `FollowMissing` | `aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors` |
| `KernelFailed` | `aos/kernel.md#/Where to send requests` (the kernel did not answer in time, or refused) |

Explained in `aos/errors/common.md#/Common error codes`: `DaemonMissing`, `InstanceMissing`, `AddRejected`, `ToolExists`, `LlmKernelMissing`.

A Code that is not here: the page of the tool that printed it (`aos/tools/<tool>.json`), or `aos/cli/errors.md#/Codes you will meet` for commands.
