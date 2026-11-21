# Commands for humans and external agents

Use these shell commands to manage agents, tools and daemon procs.

Inside aos, prefer your registered tools. Use this CLI from a human shell or an external coding agent. Every command has `--help`, and the help is the source of truth.

Choose the daemon: `--daemon D` > `$AOS_DAEMON`, then aos-agent and the others differ. aos-agent: two folders up from the agent stack it found in the current directory (`aos/cli/flags.md#/Naming the agent in aos-agent`); a tree root's `./.stack` is never taken as the daemon. aos-daemon-ctl, aos-mailbox and the other commands: `./.stack` in the current directory, no upward search. Use an absolute `AOS_DAEMON`. D is the daemon's stack, not its definition.

Choose the agent: `--target NAME` > `$AOS_AGENT` > the current directory (`./.stack`, then `./`, when it is the stack of a row on the daemon's table; `aos/cli/flags.md#/Naming the agent in aos-agent`). `ctl add` uses `--name`; `ctl rm` requires a positional name; `ctl ls` lists all; `ctl who` uses a stack.

Most aos-* commands have a page below (the index also has pointer rows for those explained inside another page); the low-level parts are in `aos/cli/parts/`. Read `aos/cli/flags.md` (where flags go) and `aos/cli/errors.md` (what to do on an error) first.
