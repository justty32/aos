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
