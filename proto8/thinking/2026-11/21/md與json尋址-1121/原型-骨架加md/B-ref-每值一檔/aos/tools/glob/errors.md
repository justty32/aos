# glob: errors

- `PatternBad`: a broken pattern, like `[` without `]` (`unclosed [ in '[a'`), or one starting with `/` (put the folder in `path`).
- `FileMissing`: no such folder. `ls` the folder above.
- `FileBad`: `path` is a file, not a folder. Give its folder, or `stat` the file.
- `ReadFailed`: the `path` folder cannot be read. Unreadable folders deeper are only counted.
- `ArgumentsBad`: also `type` not file, dir or any; `sort` not name or mtime; `max_items` outside 1 to 500; a negative `offset`.
- `WsMissing`: `aos/errors/common.json#/files`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.json#/input`.
