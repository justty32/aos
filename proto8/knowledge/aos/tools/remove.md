# Tool remove

Delete a file, link or folder for real, like `rm`. There is no undo.

- A folder needs `"recursive": true` (like `rm -r`). Without it: `FileBad`, nothing is deleted.
- A link is deleted itself; what it points to stays.
- Prints `{"path", "type"}`, and `counter_files` for a folder (every file deleted inside it).

Use `trash` unless you are sure (trash can be undone). Use remove for things you made and no longer need, and to empty the trash.

```json
{"path": ".trash", "recursive": true}
```
prints `{"path":".trash","type":"dir","counter_files":4}`.

Errors:

- `FileMissing`: nothing at that path.
- `FileBad`: a folder without `"recursive": true`. Check what is inside with `ls` before you add it.
- `PathBad`: `.`, `..` or `/` are refused.
- `RemoveFailed`: the system refused (for example no permission). In a folder, part of it may be gone already: `ls` it.
- `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
