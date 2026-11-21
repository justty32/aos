# Tool jsonx_multi_set

Like `json_multi_set`, but each item is done like `jsonx_set`: for aos configuration files that use `$ref`/`$env`. For plain data use `json_multi_set`.

- Each item: `{"path": "FILE#/POINTER"}` plus exactly one of `value` (any JSON), `text` (a JSON text, parsed), `from` (`FILE#/POINTER` to copy). Two of them, none, or any other key = that item's `[error] ArgumentsBad`; the other items are still done.
- `resolve`, `follow`, `check`, `parents`: as in jsonx_set, one setting for every item (not inside an item).
- In order, nothing undone; one line per item (`ok ...` or `[error] CODE reason`); any failed = last line `jsonx_multi_set: error: PlacesFailed ...`, exit code 1.

```json
{"items": [{"path": "fsm.json#/states/think/n", "value": 2}, {"path": "fsm.json#/states/act/exec", "from": "lib.json#/exec"}], "follow": true}
```
prints
```text
fsm.json#/states/think/n	ok fsm.json#/states/think/n
fsm.json#/states/act/exec	ok fsm.json#/states/act/exec
```

Options: `aos/tools/jsonx_set.md`. Errors: `aos/tools/json_multi_set.md#/json_multi_get, json_multi_set: errors`, `aos/tools/jsonx_set.md#/jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set: errors`.
