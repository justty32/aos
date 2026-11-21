# Tool ls

List one folder: one line per item, `NAME<TAB>TYPE` (type is `file`, `dir` or `link`). Folders come first, then files, each sorted by name.

Use it to see what is in a folder. Not for: one item in detail (`stat`), what is inside a file (`read`, `view`), finding files by name in a whole tree (`glob`), searching inside files (`grep`).

Arguments, all optional: `path` (default `.` = your workspace), `long`, `json`, `hidden`, `offset`, `max_items` (default 100, at most 500).

```json
{"path": "notes", "max_items": 1}
```
prints
```text
a.txt	file
... next_offset 1 (2 items in all)
... 1 hidden (names starting with .)
```

`... next_offset N`: there is more; call again with `"offset": N`. Names starting with `.` (like `.trash`) are hidden unless `"hidden": true`. A page with no items and no hidden names (an empty folder, or `offset` past the end) prints `... empty`.

The `long` columns and `json`: `aos/tools/ls.md#/ls: long and json`. Errors: `aos/tools/ls.md#/ls: errors`.

# ls: long and json

`"long": true` adds three columns: SIZE (bytes; files only, else `-`), MTIME (UTC), INFO.

```text
my_tool	dir	-	2026-11-11T03:17:02.222+00:00	children 2 aos _entry,_tooldef.json
notes	dir	-	2026-11-11T03:17:02.222+00:00	children 1
cfg.json	file	82	2026-11-11T03:17:02.222+00:00	keys name,states,max
```

INFO for a folder: `children N`, and `aos ...` when aos files are inside (`_entry`, `_tooldef.json`, `loop.json`, `tools.json` and so on: then the folder is a tool or an agent definition). For a file: `exec`, and for a `.json` file its top keys (`json broken` if it is not valid JSON; `json array` or `json value` if the top is not an object). Only the first 12 keys are named, then `+N`. A .json file over 1MB is not opened: no keys. A name that vanished while listing has TYPE `missing`. For a link: `-> target`.

`"json": true` prints one JSON object instead of lines: `path`, `counter_items` (all items; names starting with `.` only with `hidden`), `items` (name, type, size, mtime and the INFO facts), `next_offset`, `counter_hidden`.

# ls: errors

- `FileMissing`: no such folder. List the folder above it.
- `FileBad`: the path is a file, not a folder. Use `stat` or `read` on it.
- `ArgumentsBad`: also `max_items` outside 1 to 500, or a negative `offset`.
- `ReadFailed`, `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
