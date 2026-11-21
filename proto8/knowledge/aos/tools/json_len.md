# Tool json_len

The length of one place of a JSON file, as one integer: an object = how many keys, an array = how many items, a string = how many characters (not bytes; `"小明ab"` is 4).

```json
{"path": "cfg.json#/tags"}
```
prints `2`.

- A number, boolean or null has no length: `TargetBad` (`cfg.json#/max is a number; only objects, arrays and strings have a length`).
- Want the keys or items too: `json_ls` (its first line is the type and length).

Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/json_get.md#/json_get, json_ls, json_search: errors`, plus `TargetBad`.
