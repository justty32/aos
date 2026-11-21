# Tool mkdir

Create a folder, with any missing parent folders. A folder that is already there is fine. Prints `{"path", "created"}`.

```json
{"path": "a/b/c"}
```
prints `{"path":"a/b/c","created":true}`; the same call again prints `{"path":"a/b/c","created":false}`.

You often do not need it: `write`, `copy` and `move` create the parent folders themselves. Use mkdir for an empty folder, or to check that a folder exists before many writes.

Errors:

- `FileBad`: a file is at that path (`cfg.json is already a file`).
- `MkdirFailed`: the folder could not be made: a file is in the middle of the path (`cfg.json/sub: Not a directory`), or no permission. Check the path with `stat`.
- `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
