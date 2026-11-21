# Tool jsonx_get

Like `json_get`, for aos configuration files that use `$ref`/`$env` (a definition's fsm.json, tools.json, llm.json). For plain data use `json_get`.

- `"follow": true`: go through `$ref` objects on the way to the value.
- `"resolve": true`: the value with the `$ref`/`$env` inside it resolved, as aos reads it.
- `max_bytes`, `full`, the `[too big]` line: as in json_get.

fsm.json `{"states": {"think": {"$ref": "lib.json"}, "act": {"next": "think"}}}`, lib.json `{"exec": ["python3", "x.py"], "n": 1}`:
```json
{"path": "fsm.json#/states/think/exec", "follow": true}
```
prints `["python3","x.py"]` (json_get says `PointerMissing`: a directive on the way). `{"path": "fsm.json#/states", "resolve": true}` prints `{"think":{"exec":["python3","x.py"],"n":1},"act":{"next":"think"}}`.

Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`.
