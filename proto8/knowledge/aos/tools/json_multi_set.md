# Tool json_multi_set

Set several places at once: like `json_set` for each item, in the order given. Each item is `{"path": "FILE#/POINTER", "value": any JSON}`; values are stored exactly as given, `.../-` appends. One line per item: the path, a TAB, then `ok ...` or `[error] CODE reason`.

```json
{"items": [{"path": "cfg.json#/max", "value": 30}, {"path": "cfg.json#/tags/-", "value": "c"}]}
```
prints
```text
cfg.json#/max	ok cfg.json#/max
cfg.json#/tags/-	ok cfg.json#/tags/2
```

- Items are done one by one and nothing is undone: if item 2 fails, item 1 stays written and item 3 is still done. Any failed = a last line `json_multi_set: error: PlacesFailed N of M ...`, exit code 1; fix only the `[error]` lines and send those again.
- Later items see what earlier ones wrote (same file is fine).
- `"parents": true` applies to every item (not to a `/-` item: that array must exist). One place only: `json_set`. Path: `aos/tools/json_get.md#/JSON tools: the path`.

# json_multi_get, json_multi_set: errors

- `[error] CODE reason` on one line: that place failed with the code json_get or json_set would give (`aos/tools/json_get.md#/json_get, json_ls, json_search: errors`, `aos/tools/json_set.md#/json_set, json_add, json_del: errors`); the other places are not affected.
- `PlacesFailed` (last line, exit code 1): how many places failed. The rest were done; nothing is undone. Send again only the failed ones.
- `ArgumentsBad` (only line): `paths` / `items` is not a non-empty array; nothing was done. An item that is not an object is also `ArgumentsBad` as the only line. Inside an item (no `path`, unknown key, no `value`): that item's `[error]` line.
