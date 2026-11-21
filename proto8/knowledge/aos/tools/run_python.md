# Tool run_python

Run a short Python 3 program and get what it prints (stdout and stderr merged). The last line is always `[exit code N]`.

Use it for calculations, parsing or reshaping data, and checks that are awkward in bash. Not for: one arithmetic expression (`math`), a change you can make with `edit` or `json_set`, shell commands (`shell`).

```json
{"code": "import json\nprint(json.dumps({\"n\": 6 * 7}))"}
```
prints
```text
{"n": 42}
[exit code 0]
```

An exception prints its traceback and `[exit code 1]`. That is your program's result, not a tool error: fix the code and run again.

How it runs: `aos/tools/run_python.md#/run_python: how it runs`. Errors: `aos/tools/run_python.md#/run_python: errors`.

# run_python: how it runs

- The current folder is your workspace, the same as `shell`: relative paths like `open("data/a.csv")` read and write there. The program itself is saved as `main.py` in this tool's own folder in your stack (`tools/run_python/`; a temporary folder if you have no stack), not in the workspace.
- Count on the standard library only. It runs as `python3 -I`: no user site packages, `PYTHON*` variables are ignored.
- Output over 8000 characters keeps the first 3000 and the last 3000, with `... (N chars omitted) ...` between.
- `timeout_s`: default 60, at most 300. Past it the whole process group is stopped.
- Killed by signal N: `[exit code 128+N]`. Exit codes: `aos/errors.md#/Exit codes`.
- It is not a sandbox: the program can touch anything your Linux user can.

# run_python: errors

- `CommandFailed`: the program ran over `timeout_s` and was stopped. What it printed so far comes before the error line. Give a bigger `timeout_s` (at most 300), or do less in one run.
- `WsMissing`: you have no workspace (`AOS_WS` is not set or not a folder). A setup problem: report it.
- `LaunchFailed`: python3 could not start. A setup problem: report it.
- `LogFailed`: the command log in your stack could not be written (`aos/errors/common.md#/Codes from file work`).
- `ArgumentsBad`: also an empty `code`, or `timeout_s` not above 0 and at most 300 (0 is refused). Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
