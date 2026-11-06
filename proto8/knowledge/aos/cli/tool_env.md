# Hub variables in tool registrations

Save hub locations at registration time so each tool call uses the intended services.

11-06 note: Register hubs with:

```sh
aos-tools --file tools.json add --name read --env-file hubs.env --envs AOS_MEMORY=/data/memory ../lib/base/read
```

These flags belong to `aos-tools add`. `aos-agent tools --target bob add` currently does not accept `--env-file` or `--envs` (`FlagUnknown`). Use aos-tools when registering hub variables.

Repeat `--envs K=V` as needed. The last value for a key wins. At registration, envs overrides the file regardless of flag order. The file path is relative to cwd. Values are literal strings; the resulting values are saved in the registry and override inherited environment at call time.

Editing hubs.env later has no effect until the registration is replaced with `--override`. Replacement rewrites the whole entry, including env. Registry values cannot override the tool's scratch `AOS_STACK`.

Missing hubs declared by the tool produce a warning and registration still succeeds. ls/get do not print stored registration env values. Tool input stays in stdin JSON; hub variables are not tool arguments. See [J3 implementation](../../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j3-aos-tools-收口).
