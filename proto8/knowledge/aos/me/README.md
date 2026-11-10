# Who am I

Finding your own name, what is in your stack, and what you are allowed to change.

You are one proc on one daemon. The daemon's table has one row for you: your name, your phase (running, stopped, sleeping), your workspace, your definition, your stack.

Your name: you do not know it from the inside. The command `aos-agent ctl who` looks at `$AOS_STACK`, finds the table row whose stack contains it, and prints the name. Tools that act on you (such as `self_tools`) do this for you, so you rarely need it yourself.

What is in your stack (`$AOS_STACK`):

- `history.jsonl`: your conversation, one JSON message per line. Append only; never rewrite it.
- `queue/`: your queue. Humans and other agents drop letters here; you answer them in order.
- `tools.json`: your own tool registry. It holds only the differences from the definition's (`"$override"` points at that file; a tool you removed is `null`). Written by tools, not by hand.
- `llm.json`: your brain overlay (for example which endpoint pack you use).
- `tools/<name>/`: a scratch folder for each tool you call.

What you may change: only your own overlays, and only through tools:

- your toolbox: tool `self_tools`, called like `{"op": "add", "name": "<name>", "path": "tools/<name>"}`; all calls and rules are in the child node `me/self_tools`.
- your brain endpoint: a human runs `aos-agent llm set endpoint=<pack>`; there is no tool for this yet.

What you may not change: the definition folder, other agents' stacks, the daemon's files, `history.jsonl` by hand.

If you need to know whether you run under a daemon at all: tools that need the daemon answer `DaemonMissing` or `InstanceMissing` when you do not. `DaemonMissing` means `AOS_DAEMON` is unset or its directory does not exist. `DaemonFailed` means the daemon is configured and its directory exists, but no reply arrived within the timeout (busy, paused or down). Then features like `self_tools`, `agents` and `thought` are unavailable for now; say so. Do not retry right away; you may try once more later.

11-06 note: The tool scratch folder is assigned by `aos-tools call`, using your stack as the parent. Brain, act and MCP callers pass their own `$AOS_STACK`; they do not append another `tools/<name>/`. Executable tools use the same stdin JSON route as folder and JSON tools. See [J3 implementation](../../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j3-aos-tools-收口).
