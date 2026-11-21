# Tool json_multi_get

Get several places at once: like `json_get` for each path, in the order given. One line per path: the path, a TAB, then what `json_get` would print (the value as one line of JSON, or the `[too big] ...` line).

```json
{"paths": ["cfg.json#/name", "cfg.json#/states/think/next", "cfg.json#/nope"]}
```
prints
```text
cfg.json#/name	"bob"
cfg.json#/states/think/next	"act"
cfg.json#/nope	[error] PointerMissing no such pointer: cfg.json#/nope (cfg.json has no nope)
json_multi_get: error: PlacesFailed 1 of 3 places failed (lines with [error] above); the others were done, nothing was undone
```

- The places are independent: one failing does not stop the others. Any failed = the last line is `PlacesFailed` and the exit code is 1; the other lines are still good.
- `max_bytes`, `full`: as in json_get, for each place. Paths may be in different files.
- One place only: `json_get`. Path: `aos/tools/json_get.md#/JSON tools: the path`. Errors: `aos/tools/json_multi_set.md#/json_multi_get, json_multi_set: errors`.
