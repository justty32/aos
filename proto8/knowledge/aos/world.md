# How the pieces fit

The mental model: daemon = hardware, stack = memory, workspace = external memory, definition = source code, kernel = gatekeeper.

Think of a small computer:

| aos word | like | where |
|---|---|---|
| daemon | the hardware; it runs procs and keeps the table of who is running | `$AOS_DAEMON` (the daemon's own stack folder) |
| stack | RAM of one running proc: its state, history, mailbox | `$AOS_STACK` |
| workspace (ws) | the disk you work on; shared with other agents when they are given the same ws | `$AOS_WS` |
| definition | the program's source code; running it makes an instance (a stack under a daemon) | the folder an agent was started from |
| kernel | the gatekeeper: decides if a proc may run; the daemon is the simplest one (it says yes to everything) | `$AOS_KERNEL` when a judge is in front of the daemon |
| llm kernel | a separate daemon that answers brain requests sent as letters | `$AOS_LLM_KERNEL` (its stack; letters go to `$AOS_LLM_KERNEL/requests/`) |
| knowledge base | a read-only folder tree you look things up in with the `memory` tool | `$AOS_MEMORY` |

Facts that follow from the model:

- One definition can run as many instances. Each instance has its own stack. Changing a stack never changes the definition.
- A definition is read-only for you. Humans edit definitions. Per-instance changes (your tools, your brain endpoint) live in your stack as an "overlay": only the differences are stored.
- A proc is always under exactly one daemon. "My daemon" is the one in `$AOS_DAEMON`. Child agents you start go on the same daemon.
- Everything persists as files, so a daemon can sleep, be copied elsewhere with its stacks and workspace, and wake up there.
- Environment variables you can rely on: `AOS_WS`, `AOS_STACK`, `AOS_DAEMON`, and, when set up for you, `AOS_LLM_KERNEL`, `AOS_KERNEL`, `AOS_MEMORY`, `AOS_TICK`, `AOS_TICK_INTERVAL`. Do not invent others.

## Time

- The tree has a clock like a board's crystal: when `AOS_TICK` is set, it names a file holding one integer, the current tick. The daemon advances it (a `_tick` row in `aos-agent ctl ls`).
- Between procs, write waits in ticks: `thought` and `agents ask` take `timeout_ticks` instead of `timeout_s` (give one, not both). With a clock, a wait ends after that many ticks; if the clock is paused or the tree sleeps, time does not pass and the wait does not expire.
- No clock (`AOS_TICK` not set): ticks fall back to wall time, 1 tick = `AOS_TICK_INTERVAL` ms (default 1000).
- Waits for people, for outside services and for Linux processes stay in seconds or milliseconds.
- Tick numbers only compare inside one tree; in letters to another tree, use milliseconds.
