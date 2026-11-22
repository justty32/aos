You are an eca (Claude Code, Codex CLI or pi runs your turns): which pages and sections of this knowledge base are for you, and which you can skip.

# Reading as an eca

Key points:

- Your CLI's own tools do files, commands and helpers; aos gives you mailbox, self, json, index and a few small tools (`aos/packs.md#/Tool packs`).
- Many pages also describe agent-fsm. Read the lines that say eca, or that say nothing about the body; skip the lines that say agent-fsm only.
- A tool a page teaches may not be in your list: `self_tools` `{"op": "ls"}` shows what you have. Tools not in the stock eca templates (self_hook, clock_register, agent_def, tools_def, jsonx_*) are added one at a time with `self_tools`.
- Something broke: `aos/troubleshooting.md`; a tool failed: `aos/errors.md`.

# Read these

- `aos/_description.md`: the eight words and five rules.
- `aos/body.md`: how an eca differs (brain, tools, hooks, screen, system text, history).
- `aos/cli/eca.md`: your own body: one turn, the screen, slash commands, external MCP servers, guarding the CLI's own tools.
- `aos/mailbox.md`: letters, and the `mail_notify` hook that tells you about new ones.
- `aos/me.md`: your name, your stack, `self_state`, `self_ctl` (`self_ctl` is off in the stock templates; add it with `self_tools`).
- `aos/me/self_tools.md`: adding and removing your own tools.
- `aos/user_zone.md`: how to ask the user.
- `aos/rules.md`: what you must not do.
- `aos/packs.md#/Tool packs`: which packs an eca has.

# Read when you need them

- `aos/me/self_hook.md`: hooks on your own events. Add `self_hook` first. On an eca, `before_tool` / `after_tool` see only aos tools, and `before_compact` / `after_compact` follow the CLI's own compaction (claude).
- `aos/clock.md`: clock letters (add `clock_register` first) and on_clock hooks.
- `aos/me/self_system.md`, `aos/me/self_llm.md`, `aos/me/self_history.md`: your system text, brain settings and history. These three tools are off in the stock templates; add them with `self_tools`. On an eca only `model` and `reasoning_effort` of your brain settings count.
- `aos/agents.md`: `agent_def` for new definitions (add it first); the `subagent` pack is not in the stock eca templates, so use your CLI's own helpers for side tasks.
- `aos/definition.md`, `aos/kits.md`: making or changing definitions (a person's job, or `agent_def`).
- `aos/status.md`, `aos/world.md`, `aos/kernel.md`: the daemon table, the mental model, kernels.
- `aos/tools/` nodes for the tools you have: the json tools, `index_view`, `math`, `peek_clock`, `peek_now_time`.

# Skip these (agent-fsm only)

- `aos/me/compact.md`: answering `[aos] compact:` and folding agent-fsm history. Your compaction is the CLI's own (`aos/cli/eca.md`).
- `aos/me/do_task.md`: an eca gets `BodyUnsupported`.
- `aos/agents/fork.md`: fork is agent-fsm only.
- `aos/brain.md`: brain letters to the llm kernel; your CLI is your brain.
- `aos/tools/` nodes of the file and shell tools (read, ls, view, stat, grep, glob, write, edit, copy, move, mkdir, trash, remove, shell, run_python) and of goal and todo: an eca has none of them; use your CLI's own.
