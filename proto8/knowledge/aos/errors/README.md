# Reading an error

How to read a failed call: the `error:` line, `warning:` lines, and exit codes.

A failed aos program prints one error line: `program: error: Code reason`.

`self_tools: error: PathBad /etc/x is an absolute path outside the tool library`

- First word = who failed (a program, a tool, or an agent name).
- The word right after `error: ` = the Code. Its ending tells the kind of problem: see child `codes`.
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
