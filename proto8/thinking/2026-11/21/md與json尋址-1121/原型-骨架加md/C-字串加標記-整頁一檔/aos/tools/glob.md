<!-- #/_description -->
# Tool glob

Find paths by name pattern under a folder: one path per line, folders end with `/`. Paste a path into `read` or `ls`.

Use it to find files by name anywhere in a tree. Not for: searching inside files (`grep`), one folder with types (`ls`), facts about one file (`stat`).

Pattern: `*` within one level, `?` one character, `[abc]` (`[!abc]`), `**` any number of levels (also zero). Without `/` it matches the name at any depth (`*.py` = every .py file); with `/` the whole path under `path` (`src/*.py` directly in src, `src/**/*.py` at any depth).

Arguments: `pattern` (required); `path` (folder, default `.`); `type` (`file` default, `dir`, `any`); `sort` (`name` default, `mtime` newest first); `hidden`; `gitignore`; `offset`; `max_items` (default 100, at most 500).

```json
{"pattern": "src/**/*.py", "max_items": 1}
```
prints
```text
src/deep/util.py
... next_offset 1 (2 paths in all)
```

`... ` lines are notes. Rules: `aos/tools/glob.json#/rules`. Errors: `aos/tools/glob.json#/errors`.

<!-- #/rules -->
# glob: what it looks at

- `"sort": "name"`: by path, each level by name (`src/deep/util.py` before `src/main.py`). `"mtime"`: newest first.
- Names starting with `.` only with `"hidden": true`, or when the pattern names them (`.github/**`, `**/.env`).
- In a git work tree, `.gitignore`d paths (`build/`, `node_modules/`) and `.git` are left out; `"gitignore": false` keeps them. No git = a warning, nothing left out.
- A link to a folder is listed (with `/`) but not looked into: no loops. A `path` that is a link is followed. A broken link is not listed. Other kinds (fifo, socket) are listed only with `"type": "any"`.
- `... next_offset N`: call again with `"offset": N`. `... no matches`; `... no matches from offset N` = `offset` is past the last path. `... skipped N unreadable`: folders it could not open.
- Scan budget: 20 s or 20000 names, then `... stopped after ...`; totals say `at least`. Narrow `path`.

<!-- #/errors -->
# glob: errors

- `PatternBad`: a broken pattern, like `[` without `]` (`unclosed [ in '[a'`), or one starting with `/` (put the folder in `path`).
- `FileMissing`: no such folder. `ls` the folder above.
- `FileBad`: `path` is a file, not a folder. Give its folder, or `stat` the file.
- `ReadFailed`: the `path` folder cannot be read. Unreadable folders deeper are only counted.
- `ArgumentsBad`: also `type` not file, dir or any; `sort` not name or mtime; `max_items` outside 1 to 500; a negative `offset`.
- `WsMissing`: `aos/errors/common.json#/files`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.json#/input`.
