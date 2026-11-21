# Tool shell

Run one bash command line. The current folder is your workspace. stdout and stderr come back merged; the last line is always `[exit code N]`.

Use it to count (`wc -l`), run programs and tests, and use git or pipes. Not for: searching (`grep` for file contents, `glob` for file names: their output is paged and will not flood you), reading a file (`read`, `view`), listing one folder (`ls`), changing a file (`write`, `edit`, `json_set` are exact and checked). For Python code: `run_python`.

```json
{"command": "grep -rn two notes"}
```
prints
```text
notes/b.txt:2:line two
notes/a.txt:2:line two

[exit code 0]
```

A non-zero `[exit code N]` is your command's result, not a tool error: `grep` that finds nothing prints `(no output)` and `[exit code 1]`. Read the output, it is the answer.

How it runs: `aos/tools/shell.md#/shell: how it runs`. Errors: `aos/tools/shell.md#/shell: errors`.

# shell: how it runs

- `timeout_s`: default 30, at most 300. Past it the whole process group is stopped and the call fails with `CommandFailed`.
- Long output keeps the last 2000 lines or 50KB, with a note line `[output too long; kept the last N lines (limit 2000 lines or 50KB)]`. Pipe into `head` or `tail` to choose the part.
- stdin is empty: a command that asks a question gets no answer. Use its `-y` or `--yes` style flag.
- Each call is a new bash: `cd` and variables do not carry over. Write `cd notes && ls` in one command.
- Killed by signal N: `[exit code 128+N]`. More on exit codes: `aos/errors.md#/Exit codes`.
- It is not a sandbox: the command can touch anything your Linux user can. Be careful with `rm`; prefer the `trash` tool.

# shell: errors

- `CommandFailed`: the command ran over `timeout_s` and was stopped (`ran over 30 s; stopped the whole process group`). The output so far comes before the error line. Give a bigger `timeout_s` (at most 300), or make the command do less.
- `LaunchFailed`: bash could not start. A setup problem: report it.
- `LogFailed`: the command log in your stack could not be written (`aos/errors/common.md#/Codes from file work`).
- `ArgumentsBad`: also an empty `command`, or `timeout_s` not above 0 and at most 300 (0 is refused).
- `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
