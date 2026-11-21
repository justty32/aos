# Tool edit

Change part of a text file by exact replacement. Each item of `edits` is `{"old_text": "...", "new_text": "..."}`.

Rules: each `old_text` is matched against the file as it was before this call. It must occur exactly once, character for character (spaces, tabs and newlines too). Items must not overlap. If one item fails, nothing is changed.

Use it for a few changes in a file you have read. Not for: a new file or a full rewrite (`write`), values in a JSON file (`json_set` is safer).

```json
{"path": "out/hello.txt", "edits": [{"old_text": "world", "new_text": "there"}]}
```
prints `In out/hello.txt, replaced 1 places (first at line 2)`.

- `read` the file first and copy `old_text` from it exactly.
- Keep `old_text` short but unique: when it occurs more than once, add the line before or after it.
- Delete text: `"new_text": ""`.
- A file with Windows line ends (CRLF) works: write `old_text` with `\n`; the CRLF ends are kept (if even one line end is CRLF, all are written CRLF).
- A link: the file it points to is changed.

Errors: `aos/tools/edit.md#/edit: errors`.

# edit: errors

Nothing is changed when any of these happens.

- `TextMissing`: an `old_text` is not in the file. Usual causes: different spaces or indentation, tabs against spaces, a line end, or the file changed since you read it. `read` it again and copy the text exactly.
- `TextBad`: an `old_text` occurs N times (add the lines around it until it is unique); an `old_text` is empty; two items overlap (merge them into one); or the file would stay the same.
- `FileMissing`: no such file, or the path is a folder (use `write` for a new file). `FileBad`: not a UTF-8 text file.
- `ArgumentsBad`: also `edits` empty, or an item without the two strings.
- `ReadFailed`, `WriteFailed`, `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
