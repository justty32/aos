# Tool move

Move or rename a file, folder or link. Prints `{"from", "to"}`.

- `to` is the full new path, not the folder to move into: `{"from": "a.txt", "to": "old/a.txt"}`. Parent folders are created.
- `to` must not exist, else `FileBad` and nothing moves. To replace a file: `trash` the old one, then move.
- A link is moved itself, not what it points to. Across disks it copies and then deletes, like `mv`.

Use it to rename, to relocate, and to undo a `trash`: trash prints where the thing went (`"to": ".trash/20261111-111744/out/hello.txt"`); move it back:

```json
{"from": ".trash/20261111-111744/out/hello.txt", "to": "out/hello.txt"}
```
prints `{"from":".trash/20261111-111744/out/hello.txt","to":"out/hello.txt"}`.

To keep the original too, use `copy`.

Errors: `aos/tools/move.md#/move: errors`.

# move: errors

- `FileMissing`: `from` is not there.
- `FileBad`: `to` already exists. Pick another path, or `trash` what is at `to` first.
- `PathBad`: `to` is inside `from` (a folder cannot move into itself).
- `MoveFailed`: the system refused (permissions, something in the way). Look at both paths with `stat` before you retry. See `aos/errors/common.md#/Codes from file work`.
- `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
