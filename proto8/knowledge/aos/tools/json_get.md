# Tool json_get

Get the value at one place in a JSON file, printed as one line of compact JSON.

Use it to read one value. Not sure what is inside: `json_ls` first. Find a key or a value: `json_search`. Raw text: `read`.

```json
{"path": "cfg.json#/states/think"}
```
prints `{"next":"act"}`.

Bigger than `max_bytes` (default 8000, or env `AOS_JSON_MAX_BYTES`): one line instead
```text
[too big] object, 5 keys, 113 bytes (max_bytes 20). List it: json_ls cfg.json. Or get a deeper path, or give "full": true.
```
`"full": true` prints it however big. `$ref`/`$env` objects come back as written, and are not gone through (that is `jsonx_get`).

Path (`FILE#/POINTER`): `aos/tools/json_get.md#/JSON tools: the path`. A `.md` file: `aos/tools/json_get.md#/JSON tools: reading markdown`. Errors: `aos/tools/json_get.md#/json_get, json_ls, json_search: errors`.

# JSON tools: the path

Every json_* and jsonx_* tool takes `path`: one string `FILE#/POINTER`, e.g. `cfg.json#/states/think/next`.

- FILE alone is the whole document (`FILE#` with nothing after it is the error `SpecBad`). `FILE#/` is the top-level key whose name is empty (RFC 6901, the same as `$ref` and aos-json). A relative FILE starts at your workspace.
- After `#` the pointer starts with `/`: keys joined by `/`, array items by number (`/tags/0`, no leading zero). Inside a key `~1` = `/` and `~0` = `~` (json_ls prints keys this way).
- Ending in `/-` (json_set, json_add): after the last array item.
- Written exactly as given: quotes are not taken off (`cfg.json#"/max"` is `PointerBad`).

# JSON tools: reading markdown

The json tools that read (json_get, json_ls, json_len, json_search, json_multi_get) also take a `.md` file. Nothing is added to the markdown: the path follows what is already there. They never write markdown: change a `.md` file with `edit` or `write`.

- `FILE.md` alone is the whole text.
- `FILE.md#/Heading` is the section under that heading: the heading line, its text and its sub-sections. The first heading with that text is taken, at any level (`#`, `##` ...); exact match first, then without case. To say which one, give the parent first: `FILE.md#/Parent/Heading`. A `/` in a heading is written `~1`.
- `FILE.md#/Heading/_` is only the heading's own text: no heading line, no sub-sections. `FILE.md#/_` is the text before the first heading.
- `FILE.md#/Heading/0` is item 0 of the first list in the heading's own text (counted from 0); `/0/1` goes into the sub-list of that item. An item written `key: value` can also be taken by key: `FILE.md#/Heading/key` gives the value.
- No list there but a table: `FILE.md#/Heading/2/0` is row 2, column 0. The header row is row 0; every cell is a string, an empty cell is `""`. With a list and a table in the same text, numbers mean the list.
- A heading with nothing under it but one fenced `json` block is that JSON value: `FILE.md#/Heading/key/0` goes on inside it.
- In one place the order is: `_`, then a heading, then a number, then a list key.
- `json_ls` on `FILE.md` or `FILE.md#/Heading` lists what is under it: `_` (when there is own text), the sub-headings, then list items (the key, or the number) or table rows.
- Nothing there = `PointerMissing`; the reason lists the names that are there. If a heading was renamed, the old path stops working: look with `json_ls`.

# json_get, json_ls, json_search: errors

- `PointerBad`: nothing before `#`, or the pointer after `#` does not start with `/`.
- `PointerMissing`: no such key or array item; the reason names the level that lacks it (`cfg.json has no zzz`). Look one level up with `json_ls`. A `$ref`/`$env` object on the way is not gone through; the reason says so (use `jsonx_get` with `follow`).
- `FileMissing`: no such file. `FileBad`: a folder, not readable, or not valid JSON.
- `ArgumentsBad`: also `max_bytes`, `limit` or `depth` not a positive integer, `key` not a string, a negative `offset`, json_search with neither `key` nor `value`.
- `LaunchFailed`: the helper `aos-json` could not start (a setup problem: report it). `CommandFailed`: `aos-json` failed without a reason line.
- `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
