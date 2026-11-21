# Tool json_del

Delete one key, or one array item (later items move down). It must be there. Prints `ok FILE#/POINTER`.

```json
{"path": "cfg.json#/note"}
```
prints `ok cfg.json#/note`.

Not a whole file (`TargetBad`: use `trash` or `remove`). A `$ref`/`$env` object is a plain object here: deleting inside it changes that object. Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/json_set.md#/json_set, json_add, json_del: errors`.
