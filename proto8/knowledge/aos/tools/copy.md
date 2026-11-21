# Tool copy

Copy one file or a whole folder to a new path. Prints `{"from", "to", "counter_files"}`.

- `to` is the full new path, not the folder to copy into: to put `notes` into `backup/`, give `"to": "backup/notes"`.
- `to` must not exist yet, else `FileBad` and nothing is copied. Parent folders of `to` are created.
- Links are copied as links, not what they point to. Times and permissions are kept.

Use it to keep a backup before `write`, or to start something new from a copy. To rename or relocate, use `move`.

```json
{"from": "notes", "to": "backup/notes"}
```
prints `{"from":"notes","to":"backup/notes","counter_files":3}` (`counter_files` counts every file inside, in subfolders and hidden ones too).

Errors: `aos/tools/copy.md#/copy: errors`.

# copy: errors

- `FileMissing`: `from` is not there.
- `FileBad`: `to` already exists. Pick another path; to replace it, `trash` the old one first.
- `PathBad`: `to` is inside `from` (a folder cannot be copied into itself).
- `CopyFailed`: the system refused (permissions, disk full); nothing is left at `to`. See `aos/errors/common.md#/Codes from file work`.
- `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
