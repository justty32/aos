# Tool index_view

Show a node through its index: the notes agents keep about what is under it, one line per entry `KEY<TAB>description`. An index is a view, not the facts: entries can be missing or stale. For what is really there use `ls` or `json_ls`.

```json
{"path": "knowledge/aos/tools", "key": "json_set.md"}
```
prints
```text
[index] knowledge/aos/tools/_index.json, 58 entries
json_set.md	Tool json_set: ...
```

- Where the index of a node sits (its natural place): a folder `DIR` has `DIR/_index.json`; a JSON file `FILE` has `FILE#/_index`; an object `FILE#/POINTER` has `FILE#/POINTER/_index`. The index may also sit inside `_metainfo` as its `index` key (`DIR/_metainfo.json#/index`, `FILE#/_metainfo/index`, `FILE#/POINTER/_metainfo/index`); when both exist the one inside `_metainfo` is read first and the separate `_index` is laid over it (on the same key `_index` wins). The first line `[index] ...` always names the places read. A broken `_metainfo` (unreadable, not an object, or its `index` not an object) is skipped, not an error: the first line ends with a note like `(_metainfo.json could not be read, skipped)`.
- A key joins back to a path: `DIR/KEY` (folder), `FILE#/KEY` or `FILE#/POINTER/KEY` (JSON). Keys are printed exactly as written.
- `index` reads one index table you name (e.g. your own view). Alone: only that one. With `path`: laid over the natural index; on the same key the named one wins (the whole entry), keys only in the named one are added at the end.
- An entry may also carry `"index": PATH`, a path to another index (`cli/_index.json`, `packs.md#/_index`); it is shown as a third column `index: PATH`. An entry may hold any other keys too; index_view reads only `description` and `index` and does not print the rest (see them with `json_get`). An entry is an object (`"a.md": {"description": "..."}`), a plain string (`"a.md": "..."`: that string is the description), or `{"$ref": PATH}` (the entry or its description is read from there); this holds for `_index.json`, `_index` in a JSON file and Markdown indexes alike. Anything else (a number, an array, null) prints only the key, with no warning and exit 0. `description` is a string, or an array of strings (one line each: `{"description": ["First line.", "Second line."]}`): the lines are joined and printed on the one line of that entry, with line breaks and tabs shown as spaces. An empty array, or an array holding anything that is not a string, is not a description: only the key is printed. An `_index` inside a JSON file may itself be such a path string; then the output is one line `[index link] FILE#/_index points to PATH (not followed; ...)`. A PATH written there follows the same rules as `$ref`: left of `#` is a file path counted from the folder of the JSON file that holds it (`./`, `../`, absolute); right of `#` is inside the JSON: `#/a/b` from the root of the file, `#./b` from the object that holds the string, `#../c` from one level above that (can be repeated; above the root is bad), `#` or `#/` the whole file. `#aaa`, `y.json#./x` and `y.json#../x` are bad. The object that holds the string is, for an `_index` string, the object it sits in (`#./sub/_index` inside `FILE#/o/p/_index` is `FILE#/o/p/sub/_index`), and for the `index` of an entry, that entry itself (`_index/KEY`), so a sibling node's index is written `#../../sub/_index`. A file name with no `#` is just the file: `x.json` is `x.json` next to this file (an `_index.json` counts from its folder). The PATH printed is already joined from your workspace. Nothing is followed: to read it, call again with `{"index": PATH}`.
- `key`: only that entry (the whole key, no patterns); not there = `[no entry] KEY`.
- Markdown: a folder with no `_index.json` may have `_index.md` instead (a list of `NAME: one sentence` items; read only when there is no `_index.json`). A `.md` file, or one section of it, has its index under a heading named `_index`, or else `index`: the same kind of list. An index need not list everything in the folder.
- No natural index = `[no index] ...` (exit 0): nobody wrote a view there; use `ls` / `json_ls`. A named `index` that is missing is an error.
- Paging like json_ls: `limit` (default 200, or env `AOS_JSON_MAX_ITEMS`), `offset`, last line `[more] ...`.

To change an index, edit the place on the `[index]` line with the json tools: `json_set {"path": "d/_index.json#/a.json", "value": {"description": "..."}}` (a new folder index: first `json_set` on `d/_index.json` with value `{}`); a key that contains `/` is written with `~1`, e.g. `d/_index.json#/data.json#~1items~10` is the key `data.json#/items/0`. Delete an entry with `json_del`.

A named `index` plus `path` whose natural index is missing: the first line ends with `(natural index: ... does not exist)`. A bad `index` column on one entry prints `index: bad (...)` on that line only; the other entries are normal. The `_metainfo` note shows only when some index was read.

Errors: `IndexBad` (the index is not a JSON object, or a string that is not a valid path), `FileMissing` / `FileBad` / `PointerMissing` (the node, or the named index, is not there or not JSON), `PointerBad`, `ArgumentsBad`. Other codes: `WsMissing`, `LaunchFailed`, `CommandFailed` (`aos/tools/json_get.md#/json_get, json_ls, json_search: errors`).
