# Tool json_ls

List what is inside one place of a JSON file, like `ls`. First line: the type and length of that place. Then one line per key (or array index), ready to put after the path.

```json
{"path": "cfg.json"}
```
prints
```text
object, 5 keys
name
states
max
tags
note
```

`"long": true` adds TYPE and SIZE, TAB-separated (objects, arrays and strings also their size as one-line JSON; numbers, booleans and null show the value):
```text
object, 5 keys
name	string	4 chars	6 bytes
states	object	2 keys	47 bytes
max	number	20
```
An array starts `array, 2 items (index 0..1)`, then `0`, `1`. A plain value is one line, e.g. `number 20`.

`"depth": 2` (default 1) also lists the next level down, each line a path relative to `path` (`states`, `states/think`, `states/act`, ...), in file order; `offset` and `limit` count these lines.

Paging: `limit` (default 200, or env `AOS_JSON_MAX_ITEMS`) and `offset`. More left = last line `[more] 0 to 1 of 5 shown; next: "offset": 2`.

Path: `aos/tools/json_get.md#/JSON tools: the path`. On a `.md` file it lists the headings (and list items or table rows): `aos/tools/json_get.md#/JSON tools: reading markdown`. Errors: `aos/tools/json_get.md#/json_get, json_ls, json_search: errors`.
