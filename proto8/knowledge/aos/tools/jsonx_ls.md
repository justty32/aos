# Tool jsonx_ls

Like `json_ls`, for aos configuration files that use `$ref`/`$env`. For plain data use `json_ls`.

- `"follow": true`: go through `$ref` objects on the way to the place (a `$ref` right at the place is listed as written: one key `$ref`).
- `"resolve": true`: list the value with the `$ref`/`$env` inside it resolved, as aos reads it, e.g. `{"path": "tools.json#/tools", "resolve": true}` lists every tool after `$override`.
- `long`, `depth`, `offset`, `limit`: as in json_ls.

Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`.
