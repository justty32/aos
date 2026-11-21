# Who am I

Finding your own name, what is in your stack, and what you are allowed to change.

You are one proc on one daemon. The daemon's table has one row for you: your name, your phase (running, stuck, stopped, sleeping ...; see `aos/status.md`), your workspace, your definition, your stack.

Your name: you do not know it from the inside. The command `aos-agent ctl who` looks at `$AOS_STACK`, finds the table row whose stack contains it, and prints the name. Tools that act on you (such as `self_tools`) do this for you, so you rarely need it yourself.

What is in your stack: `aos/me.md#/What is in your stack`.

What you may change: only your own copies in your stack, and only through the `self_*` tools. They never change your definition:

- your toolbox: tool `self_tools`, called like `{"op": "add", "name": "<name>", "path": "tools/<name>"}`; all calls and rules are in `aos/me/self_tools.md`.
- your brain settings: tool `self_llm`, called like `{"op": "ls"}`; all calls and rules are in `aos/me/self_llm.md`.
- your system text: tool `self_system`, called like `{"op": "get"}`; all calls and rules are in `aos/me/self_system.md`.
- your conversation history: tool `self_history`, called like `{"op": "ls"}`; all calls and rules are in `aos/me/self_history.md`.
- one task inside your conversation, folded into a summary when done (agent-fsm only): tool `do_task`, called like `{"op": "start", "task": "..."}`; all calls and rules are in `aos/me/do_task.md`.
- compacting your agent-fsm conversation: how to answer `[aos] compact:`, what stays, and the context_wrap controls are in `aos/me/compact.md`; a `/clear` letter (your conversation starts over) is in `aos/me/compact.md#/clear: start the conversation over`.
- your hooks (programs run when something happens to you): tool `self_hook`, called like `{"op": "ls"}`; all calls and rules are in `aos/me/self_hook.md`.
- whether you go on: tool `self_ctl`, called like `{"op": "stop"}`; all calls and rules are in `aos/me.md#/Stopping yourself: self_ctl`.

An agent-fsm made from the stock template starts with `self_tools`, `self_state` and `do_task` of these; `self_llm`, `self_system`, `self_history` and `self_ctl` are off, and `self_hook` (pack events) is not in it, until you add one: `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_llm"}}` (`self_tools` `{"op": "ls", "long": true}` shows which are off). An eca made from the stock templates has `self_hook` but not `do_task`, and the same four self tools off.

To look at yourself (name, phase, tools, history size, mailbox, subagents, resources), call `self_state` with `{}`; see `aos/me.md#/Looking at yourself: self_state`.

What you may not change: your definition folder (the `self_*` tools change your copy instead), other agents' stacks, the daemon's files, `history.jsonl` by hand. Rules: `aos/rules.md`.

If you need to know whether you run under a daemon at all: tools that need the daemon answer `DaemonMissing` or `InstanceMissing` when you do not. `DaemonMissing` means `AOS_DAEMON` is unset or its directory does not exist. `DaemonFailed` means the daemon is configured and its directory exists, but no reply arrived within the timeout (busy, paused or down). With `AOS_KERNEL` set, looking up the table first asks the kernel where it is (a `procs_state_path` letter); no answer within 3 seconds = `KernelFailed`, and the tool does not fall back to `AOS_DAEMON`. Then features like `self_tools`, `subagent`, `agents_ctl` and `do_task` are unavailable for now; say so. Do not retry right away; you may try once more later.

# What is in your stack

Your stack is `$AOS_STACK`, the folder where you keep your state.

- `history.jsonl`: your conversation, one JSON message per line. Your body appends to it. Never edit it by hand; to change it use `self_history`.
- `queue/`: your queue. Humans and other agents drop letters here; you answer them in order.
- `letters.json`: `pending` = letters your body has taken and not answered yet; `dropped` = the last 50 letters it will not answer (`letter`, `reason`: `bad` letter, `blocked` by a hook, or `failed` after it was handed over; `at`). Your body writes it; `aos-agent ask` and `listen` read it, with the `aos` key of history rows (`aos/body.md#/System text, history`), to find the answer to one letter. Not by hand.
- `tools.json`: your own tool registry. It holds only the differences from the definition's (`"$override"` points at that file; a tool you removed is `null`). Written by `self_tools`, not by hand.
- `llm.json`: your brain overlay (for example which model you use). Written by `self_llm`.
- `system.txt`: your own system text, when you set one with `self_system`.
- `hookeds.json`: your own hooks, written by `self_hook`; `hookeds/<name>/`: each hook's own folder.
- `subagents.json`: your own quota change (`max_subagents`), when a human set one.
- `mailbox/`: letters to you (`aos/mailbox.md`).
- `tools/<name>/`: a scratch folder for each tool you call (made only when that tool writes something there).

Which definition files have your own copy here, and what each holds: `aos/definition.md#/Your own copy (overlay)`.

# Looking at yourself: self_state

Tool `self_state` is `aos-agent ctl state` aimed at you. It only reads; it changes nothing. It is not put into your prompt by itself: call it when you want to know.

- overview, one line per part: `{}`
- some parts in detail: `{"parts": ["history", "mailbox"]}`
- every part in detail: `{"parts": ["all"]}`
- one JSON object instead of text: add `"json": true`

The eleven parts: `who` (name, definition, workspace, stack; `parent` = the stack of who asked to add you; `notify_box` = where to report (`subagent add` sets it to the parent's `<stack>/mailbox`; null = answer the `reply_to` of the letter that gave you the work); both are what the requester wrote at add time, not proof of who started you; null when not written), `state` (phase, letters in your queue, last answer), `tools`, `llm` (brain settings), `system` (where your system text comes from, its size and first line), `hooks`, `history` (how many messages, how big, the last few), `mailbox` (letters waiting), `subagents` (agents you started with `subagent`, and your quota), `resources` (limits, memory and cpu time in use), `time` (now, how long you have been up).

It gives facts and numbers only, no advice. A part that cannot be read says `not available` and why; the other parts still show.

To change yourself use `self_tools`, `self_llm`, `self_history`, `self_hook`; to stop yourself use `self_ctl` (see `aos/me.md#/Stopping yourself: self_ctl`).

# Stopping yourself: self_ctl

Tool `self_ctl` stops, pauses, puts to sleep or removes you, the agent calling it. To do this to another agent use `agents_ctl` (see `aos/agents.md#/Any agent on the table: agents_ctl`). Every op returns as soon as the request is sent.

- `{"op": "stop"}`: you stop at the end of this step, maybe before you answer. Your stack is kept. Someone runs `aos-agent ctl start` and you carry on from there.
- `{"op": "pause"}`: you hold still after this step. Only someone else's `aos-agent ctl resume` lets you go on.
- `{"op": "sleep"}`: you stop right away, even in the middle of this turn. `aos-agent ctl wake` or a daemon restart brings you back.
- `{"op": "rm"}`: you leave the daemon table right away; your stack is kept. Only `aos-agent ctl add` brings you back.
- `{"op": "rm", "purge": true}`: also deletes your stack (your history and everything in it). This cannot be undone.

Use it when your work is done or you must not go on. Errors: ArgumentsBad, OpUnknown, PhaseBad, CtlRejected, DaemonMissing, InstanceMissing.
