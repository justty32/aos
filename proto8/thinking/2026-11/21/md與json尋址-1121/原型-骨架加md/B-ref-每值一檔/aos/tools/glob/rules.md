# glob: what it looks at

- `"sort": "name"`: by path, each level by name (`src/deep/util.py` before `src/main.py`). `"mtime"`: newest first.
- Names starting with `.` only with `"hidden": true`, or when the pattern names them (`.github/**`, `**/.env`).
- In a git work tree, `.gitignore`d paths (`build/`, `node_modules/`) and `.git` are left out; `"gitignore": false` keeps them. No git = a warning, nothing left out.
- A link to a folder is listed (with `/`) but not looked into: no loops. A `path` that is a link is followed. A broken link is not listed. Other kinds (fifo, socket) are listed only with `"type": "any"`.
- `... next_offset N`: call again with `"offset": N`. `... no matches`; `... no matches from offset N` = `offset` is past the last path. `... skipped N unreadable`: folders it could not open.
- Scan budget: 20 s or 20000 names, then `... stopped after ...`; totals say `at least`. Narrow `path`.
