# Flags for lib tools

Lib tools accept schema-derived flags as another way to supply their JSON input keys.

For example:

```sh
aos-exec lib/tools/base/read --path a.txt --max-lines 1
```

Flags override stdin keys. `--a.b V` changes only that leaf, keeping other keys under a. In a flag `-` stands for `_` in the key name (`--max-lines` = `max_lines`). A boolean key also takes `--no-KEY` for false. An array key takes its flag repeated, one item each time; the first one replaces the array from stdin. A tool definition may list `positional` keys: plain words then fill them in order. A top-level `description` key in stdin is tolerated. Unknown stdin keys give `ArgumentsBad`. Unknown flags give `FlagUnknown`. A terminal stdin is treated as `{}` without reading it. A tool written with `fn` (`@fn.tool` and `fn.main`, like `tool.py` of the tool-python skeleton) also takes `--compile [LOCATION]` (write its `_tooldef` and `_metainfo`), `--dry-run` (print both, write nothing), `--tooldef` and `--metainfo` (print one) instead of running.

Parameters, defaults and declared error codes in `--help` come from `_tooldef.json`; prose explains the results. Human commands use `aos.flags`, which shares the tokenizer in `lib/aos/tool_io.py`. This does not make human CLI flags into a stdin JSON object; stdin still carries content such as message text or tool arguments.
