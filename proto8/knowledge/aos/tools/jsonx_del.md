# Tool jsonx_del

Like `json_del`, for aos configuration files that use `$ref`/`$env`. For plain data use `json_del`.

- Without `follow`, a `$ref`/`$env` object on the way is protected: `FollowMissing`, nothing deleted. A path right at a directive deletes that directive.
- `"follow": true`: go through `$ref` and delete in the file it points to (also the matching key in every merged part).

```json
{"path": "fsm.json#/states/think/n", "follow": true}
```
prints `ok fsm.json#/states/think/n`; the key is gone from lib.json, where that `$ref` points.

Not a whole file (`TargetBad`). Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`.
