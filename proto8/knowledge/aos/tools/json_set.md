# Tool json_set

Set one place in a JSON file to `value`: replace it, or add the key if the object lacks it. `value` is any JSON and is stored exactly as given (a string stays a string). Only that part of the file is rewritten, in one atomic write.

```json
{"path": "cfg.json#/states/act/next", "value": "idle"}
```
prints `ok cfg.json#/states/act/next`.

- `.../-` appends to an array: `{"path": "cfg.json#/tags/-", "value": "c"}` prints `ok cfg.json#/tags/2` (the new item). `.../0` replaces item 0.
- FILE alone replaces the whole file, or creates it: `{"path": "new.json", "value": {}}`.
- Missing levels on the way: `"parents": true` creates objects (like mkdir -p); else `PointerMissing`.
- A `$ref`/`$env` object is a plain object here: a key set inside it changes that object, not the file it points to (that is `jsonx_set` with `follow`).

Only add, never overwrite: `json_add`. Delete: `json_del`. Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/json_set.md#/json_set, json_add, json_del: errors`.

# json_set, json_add, json_del: errors

On an error nothing is written.

- `PointerMissing`: a level on the way is missing (give `"parents": true`; with `/-` `parents` does nothing, the array must exist); an array index past the end (write `/-` to append); json_del of something that is not there.
- `FileMissing`: no such file; create it with json_set on FILE alone, e.g. value `{}`.
- `KeyExists` (json_add): the key, or the file, is already there. json_set changes it; `/-` adds to an array.
- `TargetBad`: the place cannot take that change: `/-` after something that is not an array; the parent is a plain value (a string or number); json_del of a whole file (use `trash` or `remove`).
- `ArgumentsBad`: also `value` missing. `ValueBad`: the value cannot be written as JSON.
- `WriteFailed`: writing the file failed (`aos/errors/common.md#/Codes from file work`).
- `PointerBad`, `FileBad`, `LaunchFailed`, `CommandFailed`, `WsMissing`: as in `aos/tools/json_get.md#/json_get, json_ls, json_search: errors`.
