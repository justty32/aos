# Tool grep

Search inside files with a regular expression, like `grep -rn`: one line per match, `PATH:LINE:TEXT`. Paste PATH into `read` as `path`; LINE is its `offset`.

Use it to find where a word or pattern appears in a folder tree or one file. Not for: files by name (`glob`), reading a file (`read`); pipes, counting: `shell`.

Arguments: `pattern` (required, Python `re`, per line); `path` (folder or file, default `.`); `glob` (only these files, e.g. `*.py`); `fixed`; `ignore_case`; `context` (0 to 5); `files`; `hidden`; `gitignore`; `offset`; `max_matches` (default 100, at most 500).

```json
{"pattern": "two", "path": "notes", "max_matches": 2}
```
prints
```text
notes/a.txt:2:line two
notes/b.txt:1:two words
... next_offset 2 (3 matches in 3 files in all)
... skipped 1 binary file
```

`... ` lines are notes: `next_offset N` = call again with `"offset": N`; `no matches` = nothing found; `no matches from offset N` = `offset` is past the last match. `files`, `context`: `aos/tools/grep.md#/grep: files and context`. Skips, `... stopped`: `aos/tools/grep.md#/grep: what it searches`. Errors: `aos/tools/grep.md#/grep: errors`.

# grep: files and context

`"files": true`: one line per matching file, `PATH<TAB>matching lines`; `offset` and `max_matches` count files.
```json
{"pattern": "two", "path": "notes", "ignore_case": true, "files": true}
```
prints
```text
notes/a.txt	1
notes/b.txt	2
notes/old/c.md	1
... skipped 1 binary file
```

`"context": N`: N lines before and after each match, written `PATH-LINE-TEXT` (`-` instead of `:`); groups are separated by a line `--`.
```json
{"pattern": "more", "context": 1}
```
prints
```text
notes/b.txt-1-two words
notes/b.txt:2:more
notes/b.txt-3-Two again
... skipped 1 binary file
```

# grep: what it searches

- Order: by path (each level by name), then line. Stable, so `offset` paging does not repeat.
- `... skipped`: binary files (NUL in the first 8KB), files over 8MB, files it cannot read.
- Names starting with `.` (`.git`, `.stack`) only with `"hidden": true`, or when `glob` names them (`.github/**`).
- In a git work tree, `.gitignore`d paths (`build/`, `node_modules/`) and `.git` are left out; `"gitignore": false` keeps them. No git = a warning, nothing left out.
- Links to folders are not followed; links to files are searched under the link path. A `path` that is a link or one file is searched as given (for one file, `glob` is ignored).
- One line at a time (no match across lines); an ending `\r` is dropped; non-UTF-8 bytes become replacement characters. Printed lines over 300 characters end with `…[cut]`.
- Scan budget: 20 s or 20000 names, then `... stopped after ...`; totals say `at least`. Narrow `path` or `glob`.

# grep: errors

- `PatternBad`: the regular expression does not compile; the reason has Python's message (`missing ), unterminated subpattern at position 5`). Fix it, or use `"fixed": true`. Also a bad `glob` (`glob: unclosed [ ...`).
- `FileMissing`: no such path. Check with `ls` or `glob`.
- `ReadFailed`: `path` itself cannot be read, or is not a regular file or folder. Unreadable files deeper in the tree are only counted.
- `ArgumentsBad`: also `context` outside 0 to 5, `max_matches` outside 1 to 500, a negative `offset`.
- `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
