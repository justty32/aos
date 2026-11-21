# aos tools for an external agent

Use aos-mcp to serve the tools of aos-tools registries as MCP tools over stdio (JSON-RPC: initialize, ping, tools/list, tools/call). An eca agent gets it automatically; set it up by hand only for your own MCP client.

# Serving a registry

```sh
aos-tools --file tools.json add $AOS_HOME/lib/tools/base/read
aos-mcp --ws /abs/ws tools.json
```

Register that command line in your MCP client as a stdio server; aos-tools and aos-exec must be on its PATH. Workspace = `--ws` > `$AOS_WS` (none or not a folder = `WsMissing`); stack = `--stack` > `$AOS_STACK` > `WS/.stack/`. Flags may go before or after the registries. No registry = `./tools.json`; not a file = `ToolMissing`; two registries with the same tool name = `ToolsBad`. `--own FILE` uses the agent's own registry whenever it exists; then only that one is served and the listed registries are ignored. An empty FILE is `ArgumentsBad`. `--hooks DEF` runs the before_tool / after_tool hooks of the agent definition folder DEF (not a folder = `ArgumentsBad`). More flags: run `aos-mcp --help`.

# What a call does

Each tools/call runs `aos-tools --file REGISTRY call NAME` with the arguments on stdin; stdout is the result text. A nonzero exit = `isError: true`, and a second text carries the last 2048 bytes of the tool's stderr:

```text
read: error: FileMissing no.txt
[aos] tool: read stderr (last 2048 bytes at most):
read: error: FileMissing no.txt
```

Timeout = the tool's `_metainfo` `timeout_ms`, else `--timeout-s` (default 60; a broken `timeout_ms` counts as not written and prints a warning); 0 = no limit for either. On expiry the whole process group gets TERM, then KILL 2 seconds later, and the result is `CommandFailed`. A nonzero exit with empty stdout is also `CommandFailed`, and the text says so, e.g. `read exited 1 with empty stdout`. The list is re-read on every call; when a call changed it (self_tools add), a `notifications/tools/list_changed` follows, so new tools work in the same turn. `--enable-logs` writes one line per call to `<stack>/aos-mcp-logs.jsonl` (`--logs-path FILE` elsewhere; `--logs-path` alone = `ArgumentsBad`).
