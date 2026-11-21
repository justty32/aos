# Tool jsonx_add

Like `json_add` (adds, never overwrites), for aos configuration files, with the options of `jsonx_set`: the value from exactly one of `value`, `text`, `from`; `resolve`, `follow`, `check`, `parents`. For plain data use `json_add`.

```json
{"path": "fsm.json#/states/act/x", "text": "{\"a\": true}"}
```
prints `ok fsm.json#/states/act/x`. Already there = `KeyExists`.

Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`.
