# Tool jsonx_set

Like `json_set`, for aos configuration files that use `$ref`/`$env`. For plain data use `json_set`.

- The value: exactly one of `value` (any JSON), `text` (a JSON text, parsed), `from` (`FILE#/POINTER` to copy).
- `"resolve": true`: resolve `$ref`/`$env` in the value before storing (default: stored as written).
- `"follow": true`: go through a `$ref` on the way and change the file it points to. Without it a directive on the way is `FollowMissing`; a path right at a directive replaces it whole.
- `"check": true`: refuse a change that adds problems to the configuration (`CheckFailed`, nothing written).
- `parents`, `.../-`: as in json_set. `follow` does not apply to the path in `from`: the source is read without following (`resolve` applies).

```json
{"path": "fsm.json#/states/think/n", "value": 2, "follow": true}
```
prints `ok fsm.json#/states/think/n`; the change is in lib.json, where that `$ref` points. `{"path": "fsm.json#/states/act/exec", "from": "lib.json#/exec"}` copies a value.

Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`.

# jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors

The codes in `aos/tools/json_get.md#/json_get, json_ls, json_search: errors` and `aos/tools/json_set.md#/json_set, json_add, json_del: errors` apply (`KeyExists` only in jsonx_add). Also:

- `ArgumentsBad`: not exactly one of `value`, `text`, `from` (set, add; in a multi_set item, that item's `[error]` line); `up` with `follow` or `resolve` (search).
- `TextBad`: `text` is not JSON; the reason has the parse error.
- `FollowMissing` (set, add, del only; reading without `follow` gives `PointerMissing`): a `$ref`/`$env` object on the way; give `"follow": true`, or point at the directive itself to replace it.
- `DirectiveBad`: a `$ref` cannot be read, points nowhere or goes in a circle; with `resolve`, a `$env` is not set.
- `CheckFailed`: with `check`, the change would add problems (the reason names them); nothing written.
- `TargetBad`: also, with `follow`, replacing a value merged from several files at once. `PointerMissing`: also a `$env` on the way (it cannot be gone through).
