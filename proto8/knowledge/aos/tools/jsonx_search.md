# Tool jsonx_search

Like `json_search`, for aos configuration files that use `$ref`/`$env`. For plain data use `json_search`.

- `"follow": true`: go through `$ref` objects on the way to `path`, then search below it as written.
- `"resolve": true`: search the value with `$ref`/`$env` resolved (hits inside files a `$ref` points to are found too).
- A hit is the path in the file you gave; read it with `jsonx_get` and `"follow": true`.
- `"up": true` does not work with `follow` or `resolve` (`ArgumentsBad`): the levels above a `$ref` are in another file. `key`, `value`, `contains`, `limit`: as in json_search.

Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`.
