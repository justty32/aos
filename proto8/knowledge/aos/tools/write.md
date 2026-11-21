# Tool write

Write a whole file: `content` becomes the entire file. A missing file is created, with its parent folders. An existing file is replaced completely (its permissions, like exec, are kept).

Use it for a new file, or when you mean to rewrite all of a file. Not for: a change in part of a file (`edit`; in a JSON file `json_set`), copying a file (`copy`). write does not ask: the old content is gone. If you may need it, `copy` it first.

```json
{"path": "out/hello.txt", "content": "hello\nworld\n"}
```
prints `Wrote out/hello.txt (12 bytes)`.

- Nothing is added: end `content` with `\n` if the file should end with a newline.
- A path that is a link writes the file it points to.
- The file is first written as `.NAME.tmp` next to it and then renamed, so no half-written file is left.

Errors: `aos/tools/write.md#/write: errors`.

# write: errors

- `FileBad`: the path is a folder.
- `MkdirFailed`: a parent folder could not be made: a file is in the way (`cfg.json/x` when `cfg.json` is a file), or no permission. Check the path with `stat`.
- `WriteFailed`: the system refused the write (permissions, disk full). The old file, if any, is unchanged.
- `ArgumentsBad`: also `content` missing or not a string.
- `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
