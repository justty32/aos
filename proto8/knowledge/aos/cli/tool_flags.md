# Flags for lib tools

Lib tools accept schema-derived flags as another way to supply their JSON input keys.

11-06 note: For example:

```sh
aos-exec lib/base/read --path a.txt --max-lines 1
```

Flags override stdin keys. `--a.b V` changes only that leaf, keeping other keys under a. Extra stdin keys are ignored. Unknown flags give `FlagUnknown`. A terminal stdin is treated as `{}` without reading it.

Parameters, defaults and declared error codes in `--help` come from `_tooldef.json`; prose explains the results. Human commands use `aos_flags`, which shares the tokenizer in `lib/tool_io.py`. This does not make human CLI flags into a stdin JSON object; stdin still carries content such as message text or tool arguments.

See [J1 implementation](../../../thinking/2026-11/05/json-argv/08-J1實作結果.md), [J2 implementation](../../../thinking/2026-11/05/json-argv/09-J2實作結果.md) and [J5 implementation](../../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j5-aos_flags-去重sigpipe).
