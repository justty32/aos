# Commands for humans and external agents

Use these shell commands to manage agents, tools and daemon procs.

Inside aos, prefer your registered tools. Use this CLI from a human shell or an external coding agent.

Choose the daemon: `--daemon D` > `$AOS_DAEMON` > `./.stack` in the current directory. Use an absolute `AOS_DAEMON`. There is no upward search. D is the daemon's stack, not its definition.

Choose the agent: `--target NAME` > `$AOS_AGENT`. `ctl add` uses `--name`; `ctl rm` requires a positional name; `ctl ls` lists all; `ctl who` uses a stack.

Read the node you need:

- [flags](flags.md): help levels, short names and flag placement.
- [agent](agent.md): attach, inspect, stop, sleep and find agents.
- [talk_settings](talk_settings.md): messages, screens and per-agent settings.
- [safety](safety.md): deletion, confirmation and non-terminal input.
- [errors](errors.md): error codes, timeouts and retry decisions.
- [daemon](daemon.md): direct proc control on one daemon (never through the judge); judge routing is aos-agent ctl.
- [tools](tools.md): register and call tools; scratch stacks.
- [tool_env](tool_env.md): save hub variables in registrations.
- [tool_flags](tool_flags.md): schema-derived flags for lib tools.
- [grow_screen](grow_screen.md): grow functions and use ECA screens.
