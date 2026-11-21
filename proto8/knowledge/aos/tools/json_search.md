# Tool json_search

Find keys and/or values in a JSON file, everywhere below `path`, in file order. One line per hit: `FILE#/POINTER<TAB>TYPE<TAB>SIZE`; none = `[no match]`. Paste a hit into `json_get` or `json_set` as `path`.

- `key`: exact key name. `value`: exact JSON value of the same type (`1` is not `"1"`). Both: that key with that value.
- `"contains": true`: the key, and a string `value`, match as substrings (case-sensitive). No regular expressions.
- `"up": true`: instead of below, the keys of each level above `path`, nearest level first (where is the nearest `max` around me?).
- `limit` (default 200, or env `AOS_JSON_MAX_ITEMS`); more hits = a last line `[more] ...`: narrow `path` or raise `limit`.

```json
{"path": "cfg.json", "key": "next"}
```
prints
```text
cfg.json#/states/think/next	string	3 chars	5 bytes
cfg.json#/states/act/next	string	5 chars	7 bytes
```

Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/json_get.md#/json_get, json_ls, json_search: errors`.
