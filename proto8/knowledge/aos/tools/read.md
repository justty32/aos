# Tool read

Read a text file. You get its lines as plain text (no line numbers added).

Use it for a text file you want to read, whole or in parts. Not for: a folder (`ls`), size and type of a file (`stat`), a big file you need a map of first (`view` gives an outline), one value in a JSON file (`json_get`).

Arguments: `path` (relative to your workspace, or absolute); `offset` (first line, the first line is 1); `max_lines`. An empty file prints `(empty file)`.

```json
{"path": "notes/a.txt", "offset": 2, "max_lines": 1}
```
prints
```text
line two

[1 more lines in the file. Use offset=3 to continue.]
```

One call shows at most 2000 lines or 50KB. When the output is cut, the last line says where to go on, like `[lines 1-2000 of 2500. Use offset=2001 to continue.]`: call again with that `offset`.

Errors: `aos/tools/read.md#/read: errors`.

# read: errors

- `FileMissing`: no such path. Check the name with `ls` on its folder.
- `FileBad`: the path is a folder (use `ls`), a binary file (it is not read), or the first line to print is over 50KB (the reason gives a `shell` command that prints a part of it).
- `ArgumentsBad`: also `offset` or `max_lines` below 1 or not a whole number; and when `offset` is past the end of the file; the reason gives the number of lines.
- `ReadFailed`, `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
