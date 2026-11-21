# Tool json_add

Add something new to a JSON file; it never overwrites. Prints `ok FILE#/POINTER`.

- In an object: adds the key. Already there = `KeyExists` (json_set changes it).
- In an array: `.../2` inserts before item 2 (later items move up); `.../-` appends.
- FILE alone creates the file; an existing file = `KeyExists`.
- `"parents": true` creates missing objects on the way.

```json
{"path": "cfg.json#/tags/0", "value": "first"}
```
prints `ok cfg.json#/tags/0`; the old item 0 is now item 1.
`{"path": "cfg.json#/max", "value": 3}` when `max` is there fails with `json_add: error: KeyExists cfg.json#/max already exists; use json_set to change it`.

`value` is stored exactly as given, as in json_set. Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/json_set.md#/json_set, json_add, json_del: errors`.
