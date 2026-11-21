# Who am I

Finding your own name, what is in your stack, and what you are allowed to change.

You are one proc on one daemon. The daemon's table has one row for you: your name, your phase (running, stuck, stopped, sleeping ...; see `aos/status.json`), your workspace, your definition, your stack.

Your name: you do not know it from the inside. The command `aos-agent ctl who` looks at `$AOS_STACK`, finds the table row whose stack contains it, and prints the name. Tools that act on you (such as `self_tools`) do this for you, so you rarely need it yourself.

What is in your stack: `aos/me.json#/stack`.

What you may change: only your own copies in your stack, and only through the `self_*` tools. They never change your definition:

- your toolbox: tool `self_tools`, called like `{"op": "add", "name": "<name>", "path": "tools/<name>"}`; all calls and rules are in `aos/me.json#/self_tools`.
- your brain settings: tool `self_llm`, called like `{"op": "ls"}`; all calls and rules are in `aos/me.json#/self_llm`.
- your system text: tool `self_system`, called like `{"op": "get"}`; all calls and rules are in `aos/me.json#/self_system`.
- your conversation history: tool `self_history`, called like `{"op": "ls"}`; all calls and rules are in `aos/me.json#/self_history`.
- one task inside your conversation, folded into a summary when done (agent-fsm only): tool `do_task`, called like `{"op": "start", "task": "..."}`; all calls and rules are in `aos/me.json#/do_task`.
- compacting your agent-fsm conversation: how to answer `[aos] compact:`, what stays, and the context_wrap controls are in `aos/me.json#/compact`.
- your hooks (programs run when something happens to you): tool `self_hook`, called like `{"op": "ls"}`; all calls and rules are in `aos/me.json#/self_hook`.
- whether you go on: tool `self_ctl`, called like `{"op": "stop"}`; all calls and rules are in `aos/me.json#/self_ctl`.

An agent-fsm made from the stock template starts with `self_tools`, `self_state` and `do_task` of these; `self_llm`, `self_system`, `self_history` and `self_ctl` are off, and `self_hook` (pack events) is not in it, until you add one: `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_llm"}}` (`self_tools` `{"op": "ls", "long": true}` shows which are off). An eca made from the stock templates has `self_hook` but not `do_task`, and the same four self tools off.

To look at yourself (name, phase, tools, history size, mailbox, subagents, resources), call `self_state` with `{}`; see `aos/me.json#/self_state`.

What you may not change: your definition folder (the `self_*` tools change your copy instead), other agents' stacks, the daemon's files, `history.jsonl` by hand. Rules: `aos/rules.json`.

If you need to know whether you run under a daemon at all: tools that need the daemon answer `DaemonMissing` or `InstanceMissing` when you do not. `DaemonMissing` means `AOS_DAEMON` is unset or its directory does not exist. `DaemonFailed` means the daemon is configured and its directory exists, but no reply arrived within the timeout (busy, paused or down). With `AOS_KERNEL` set, looking up the table first asks the kernel where it is (a `procs_state_path` letter); no answer within 3 seconds = `KernelFailed`, and the tool does not fall back to `AOS_DAEMON`. Then features like `self_tools`, `subagent`, `agents_ctl` and `do_task` are unavailable for now; say so. Do not retry right away; you may try once more later.
