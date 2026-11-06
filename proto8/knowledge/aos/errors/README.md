# Reading an error

How to read a failed call: the `error:` line, `warning:` lines, and exit codes.

A failed aos program prints one error line: `program: error: Code reason`.

`self_tools: error: PathBad /etc/x is an absolute path outside the tool library`

- First word = who failed (a program, a tool, or an agent name).
- The word right after `error: ` = the Code. Its ending tells the kind of problem: see child `codes`; the most common Codes: child `common`.
- The rest = the reason, for humans. A usage hint comes last: `(usage: ...)`.

A tool you call prints the error line on stdout too, and exits 1.

`program: warning: sentence` is not an error. The call worked; the line only tells you something. Never retry because of a warning.

Exit codes:

- `0`: done.
- `10`: done, and the answer is "nothing" (no letter, no lock, no reply yet, a check found problems). Not an error: act on the "nothing".
- `130`: stopped by Ctrl-C. `128+N`: killed by signal N (`143` = TERM, often a timeout).
- other non-zero: failed. If its stderr has `itsname: error:`, the program itself failed; if not, the code came from something it ran.

Tools that run your command (`bash`, `run_python`) end stdout with `[exit code N]`: the exit code of your command, not of the tool. Non-zero there means your command failed; read its output, it is the answer.

A tool that answers with text but no error line succeeded, even if the text says "no", "none" or "(none)".

11-06 note（11-06 註）: Tool flags that cannot be parsed add `(see NAME --help)` to the reason; stdin JSON errors do not. `--help` lists schema parameters and declared error codes. In agent-fsm, a failed or timed-out tool result also includes the last 2048 bytes of its stderr; a successful result does not. The full stderr is forwarded when the tool finishes. A timeout uses `_metainfo.time_ms.max` (absent means no limit) and stops the tool's process group. See [J1 implementation](../../../thinking/2026-11/05/json-argv/08-J1實作結果.md) and [J4 implementation](../../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j4-一支兩形與格).

11-06 note（11-06 註）: Human Python commands using `aos_flags.run` exit quietly with 141 when their stdout pipe has no reader. This does not turn a failed write to a child process's stdin into 141. See [J5 implementation](../../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j5-aos_flags-去重sigpipe).
