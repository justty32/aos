# Tool jsonx_multi_get

Like `json_multi_get`, but each place is read like `jsonx_get`: for aos configuration files that use `$ref`/`$env`. For plain data use `json_multi_get`.

- `"follow": true`, `"resolve": true`, `max_bytes`, `full`: as in jsonx_get, one setting for every place.
- One line per path: the path, a TAB, then the value (or `[too big] ...`, or `[error] CODE reason`); any failed = last line `jsonx_multi_get: error: PlacesFailed ...`, exit code 1.

```json
{"paths": ["fsm.json#/states/think/exec", "fsm.json#/states/act/next"], "follow": true}
```
prints
```text
fsm.json#/states/think/exec	["python3","x.py"]
fsm.json#/states/act/next	"think"
```

Options: `aos/tools/jsonx_get.md`. Lines and `PlacesFailed`: `aos/tools/json_multi_get.md`. Errors: `aos/tools/json_multi_set.md#/json_multi_get, json_multi_set: errors`, `aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`.
