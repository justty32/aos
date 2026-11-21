# External MCP tools frozen into aos

Use aos-mcp-import to connect once to an external MCP server and freeze its tools into the server file; a definition's tools.json then stacks that file like a pack. Brains of both bodies (agent-fsm, eca) call them as normal aos tools. An eca agent can instead let its CLI connect to the server itself (`aos/cli/eca.md#/External MCP servers (claude and codex)`). Pick one way per server.

# Where an external tool comes from

A tool whose description starts with `[MCP server NAME]` is an external tool. Its name is `<server>_<tool>` (lowercase; other characters become `_`, and runs of `_` become one; at most 64 characters, else `NameBad`); through aos-mcp it is `mcp__aos__<server>_<tool>`.

- It lives in a server file that aos-mcp-import filled in: `mcp_tools` has one frozen entry per tool, `tools` registers them, and the definition's tools.json lists the file in `"$override"`.
- Each call starts the server (stdio) or opens a new session (http), calls the tool once and closes it. Nothing is kept between calls, so a server that needs a login or an open browser does not work this way.
- Description and parameters are the ones from import time.
- It is a normal aos tool: `before_tool` / `after_tool` hooks see it, and `self_tools {"op": "rm", "name": "time_get_current_time"}` turns one off.
- Output: text in order, cut after 2000 lines or 50KB; images and audio are saved in your stack: `[image saved: $AOS_STACK/tools/<tool name>/image-xxxx.png (image/png, 12345 bytes)]`; `$AOS_STACK` there is your own stack.

# Importing a server

Write the server file first (`description` + `mcp_server`, the same file eca reads), then:

```sh
aos-mcp-import --only get_current_time mcp/time.json
# imported 1 of 2 tools from time -> mcp/time.json
# add it to tools.json "$override": "mcp/time.json"
```

Then the definition's tools.json: `{"$override": ["<the packs it had>", "mcp/time.json"], "tools": {}}`. The import does not change tools.json.

- `--only A,B` / `--except C,D` are written into `mcp_server.only` / `except`. None of them = the file's own `only` / `except`, else all tools (a warning above 20). A flag that disagrees with the file, or both flags = `ArgumentsBad`.
- Two tools that become the same name = `NameBad`; leave one out with `--except`.
- A stdio server always starts in the server file's folder (at import, sync and every call): relative paths in `command` and `args` are from there. It gets the full environment of the caller, API keys included.
- The server name (`mcp_server.name`) is `[a-z][a-z0-9_]{0,31}` and not `aos`, else `PackBad`. Each frozen tool gets `timeout_ms` 60000; edit it by hand per tool.
- `--timeout-s N`: the limit for starting the server and for each page of the tool list (default 30).
- Put the file in place before you list it in `"$override"`: a missing file = `PathMissing`, and the whole registry cannot be read. A file not imported yet adds no tools.
- A file that was already imported = `PackExists`; use sync.

# Refreshing the frozen tools

```sh
aos-mcp-import sync mcp/time.json        # prints the differences, writes nothing
aos-mcp-import sync --yes mcp/time.json  # writes them
```

Lines: `+ NAME` (new), `- NAME` (gone; its registry entry goes too), `~ NAME: description changed` or `parameters changed` with a `before:` and an `after:` line. No differences = `no changes`. Differences without `--yes` end with `run again with --yes to write`; with `--yes` the last line is `synced N of M tools from SERVER -> FILE`. `--timeout-s` works as in import. Only description and parameters are compared. A `timeout_ms` you edited by hand is kept. sync uses the file's `only` / `except`: after you edit them, run `sync --yes`. A file never imported = `PackBad`. A file renamed or copied under another name after its import is also `PackBad`: its tools still run the file it was imported as, so remove its `mcp_import`, `mcp_tools` and `tools` keys and import it again (moving it to another folder under the same name is fine).

# Through aos or by the CLI itself

| | through aos (aos-mcp-import + tools.json) | the eca CLI itself (cli.json `mcp_servers`) |
|---|---|---|
| descriptions | frozen at import; refresh with sync | live, read when the CLI starts |
| hooks | `before_tool` / `after_tool` see the calls | not seen by aos |
| turn one tool off | `self_tools rm`, `aos-agent tools` | `only` / `except` in the server file |
| server process | a new one for every call | one while the CLI runs |
| bodies | agent-fsm and eca | eca only |

Using both for one server gives the brain two names for the same tool (`mcp__time__x` and `mcp__aos__time_x`): pick one. Through aos, http accepts only a Bearer token; `bearer_token_env` needs `env_file` (`PackBad` without it). `env_file` now uses the same dotenv subset as aos-tools env files: `${X}` expansion, inline `#` comments and strict matching quotes; `A=x # note` reads as `x`, then `B=${A}y` reads as `xy`. Keep env files `chmod 600`, outside the definition and the workspace. Behind a proxy, set `NO_PROXY=<host>` for a local http server.

# Codes from external MCP tools

The first word says who failed: `mcp_tool` (one call) or `aos-mcp-import`.

- `ServerFailed`: the server did not start talking, died, timed out while starting, or answered with an error (its message follows). Retry once.
- `ArgumentsBad`: the server rejected the arguments (JSON-RPC -32602). The server also answers this way when the tool is no longer there: if the arguments look right, a person runs `aos-mcp-import sync`.
- `ServerBad`: the server's answer broke the MCP protocol. Report it; do not retry.
- `ServerRejected`: http 401 or 403: the token is wrong or not allowed. A person fixes the env file; do not retry.
- `CallFailed`: the tool ran and said it failed; its own text comes first. Read it, fix your arguments, or report.
- `CommandMissing`: the server program could not be started. `CommandFailed`: the call ran past `timeout_ms`.
- `ToolUnknown`: the name is not in the server file (`mcp_tool`), or `--only` names a tool the server lacks (import).
- `NameBad`: a server or tool name does not make a valid tool name.
- Also: `WriteFailed` (the server file cannot be written), `FlagUnknown` (unknown flag), `StackMissing` (`mcp_tool` without `$AOS_STACK`).
- `PackExists`: the file was imported already; use sync.
- `PackBad`, `PackMissing`, `DotenvBad`, `PathMissing`: the server file or its env file is broken or missing (`PathMissing`: `env_file` or `ca_file` not found); a person fixes it.

More flags: run `aos-mcp-import --help`.
