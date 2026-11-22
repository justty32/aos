Common failures: one item per symptom, its cause, and how to check. Only failures that were checked against the code or the page that explains them.

# Common failures

Key points:

- Find your symptom below; each item says the cause and how to check, and points to the page with more.
- A tool failed with an `error:` line: read the Code first (`aos/errors.md`).
- A refusal (budget, kernel, quota) is a decision, not a bug: report it or adapt, do not force it.
- Your symptom is not here and you found the cause: tell eca-aos-kb, so it can be added.

# Tools and paths

- **A file path with `$AOS_HOME` in it is not found.** Cause: file tools do not expand variables. Check: get the value once with the shell (`echo $AOS_HOME`) and use the full path.
- **A tool you just added is not there.** Cause: a tool added with `self_tools` can be called from your next reply, not in the same reply. Check: `self_tools` `{"op": "ls"}` in the next reply (`aos/me/self_tools.md`).
- **`self_tools` add answers `PathMissing`.** Cause: the folder does not exist; a relative path starts at your workspace. Check: give the path with `path_json` from `$AOS_HOME`, like `{"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_hook"}` (`aos/me/self_tools.md#/self_tools: rules and errors`).
- **A page tells you to call a tool you do not have** (self_hook, clock_register, agent_def, tools_def, jsonx_*, subagent ...). Cause: that pack is not in your definition. Check: `self_tools` `{"op": "ls", "long": true}`; add the tool one at a time (`aos/packs.md#/Tool packs`).
- **`do_task` answers `BodyUnsupported`.** Cause: you are an eca; your CLI keeps tool calls outside your history. Check: use your CLI's own helpers, or `subagent` if your definition has it (`aos/me/do_task.md`).

# Hooks and timers

- **An aos `before_tool` hook does not see Bash, Write or Edit (eca).** Cause: on an eca, aos hooks see only aos tools. Check: guard the CLI's own tools with the CLI's own hooks (`aos/cli/eca.md#/Guarding the CLI's own tools (claude)`).
- **`peek_clock` or `clock_register` answers `ClockMissing` on a screen, although the tree has a clock.** Cause: the screen was opened before your loop ran once and took `AOS_CLOCK` from that person's shell. Check: have the screen closed and opened again (`aos/clock.md#/Clock letters: rules`).
- **An on_clock hook never runs.** Cause: no clock (`AOS_CLOCK` not set and no `clock` key); your log has one warning line `hook NAME (event on_clock) is not checked: AOS_CLOCK is not set ...`. Check: that line in your `stderr.txt` (`aos/me/self_hook.md#/The on_clock hook`).
- **A letter came but you were not told.** Cause: `mail_notify` looks at your mailbox once a minute, and not while you sleep or wait for the CLI. Check: `mailbox_peek`; with `self_hook` added, `{"op": "get", "name": "mail_notify"}` shows whether it is on (`aos/mailbox.md#/Hearing about new letters`).

# Daemon and kernel

- **`self_*` tools answer `DaemonMissing` or `InstanceMissing`.** Cause: `AOS_DAEMON` is unset or its folder does not exist, or there is no table row for you. Check: say so and try at most once more later (`aos/errors/common.md`).
- **mailbox, clock and `self_*` tools all fail with `KernelFailed`.** Cause: `$AOS_KERNEL` is set and the kernel did not answer within 3 s, for example a `kernel_gate` agent in a long turn or asleep. Check: wait and try again once; if it keeps failing, report that the kernel is not answering (`aos/kernel.md#/Where to send requests/When the kernel is slow or busy`).
- **`BudgetMissing ... max_calls N reached in this window`.** Cause: the brain budget of this window is used up. Check: the error's `resets_at` says when the next window starts (`aos/brain.md#/Priority and budgets`).
- **`SubagentSlotMissing`.** Cause: your subagent quota is full; nothing was started. Check: `rm` a subagent you no longer need, or say the limit is reached (`aos/agents/subagent.md`).

# The overview page (aos-frontend)

- **The page shows `aos-agent ctl ls --json failed`.** Cause: `$AOS_HOME/frontend/bin/aos-frontend` reads the daemon table with `aos-agent ctl ls --json`, run from `/` with the environment the page was started with. Without `AOS_DAEMON` there, or without `aos-agent` on its PATH (the tree's `env.sh` not sourced), the call fails, and the page does not show the command's own error. Check: in the shell that started the page, `echo $AOS_DAEMON` and `command -v aos-agent`; start it again after `source env.sh` with `AOS_DAEMON` set. The systemd unit `$AOS_HOME/frontend/systemd/aos-frontend.service` sets both itself.
