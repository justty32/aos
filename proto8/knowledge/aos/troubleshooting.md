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
- **An eca's background Bash (a `sleep` used as a timer, a long build) stops without finishing, and nothing comes of it.** Cause: with the screen closed (`claude -p`), the turn ends at the first answer; a background task still running 3 s later is stopped together with the CLI (SIGTERM, then SIGKILL; not with `"live_mail": true`). Check: whether the task was started with run_in_background in a turn that has already ended. Use `clock_register` for timers, and run long commands in the foreground (`aos/clock.md#/Doing something on a timer: which way`).
- **A letter came but you were not told.** Cause: `mail_notify` looks at your mailbox once a minute, and not while you sleep or wait for the CLI. Check: `mailbox_peek`; with `self_hook` added, `{"op": "get", "name": "mail_notify"}` shows whether it is on (`aos/mailbox.md#/Hearing about new letters`).

# Daemon and kernel

- **`self_*` tools answer `DaemonMissing` or `InstanceMissing`.** Cause: `AOS_DAEMON` is unset or its folder does not exist, or there is no table row for you. Check: say so and try at most once more later (`aos/errors/common.md`).
- **mailbox, clock and `self_*` tools all fail with `KernelFailed`.** Cause: `$AOS_KERNEL` is set and the kernel did not answer within 3 s, for example a `kernel_gate` agent in a long turn or asleep. Check: wait and try again once; if it keeps failing, report that the kernel is not answering (`aos/kernel.md#/Where to send requests/When the kernel is slow or busy`).
- **A kernel's hooks never run, and its log has `kernel.json has a top-level "hooks" key, which is ignored`.** Cause: the hooks are written in `kernel.json` under `"hooks"`; both the llm kernel and the kernel station ignore that key. Check: move them into the file named by `"hookeds"` in the `interfaces.json` next to `kernel.json` (the templates use `kernel_hookeds.json`) and delete the key (`aos/cli/parts/llm_kernel.md`).
- **`BudgetMissing ... max_calls N reached in this window`.** Cause: the brain budget of this window is used up. Check: the error's `resets_at` says when the next window starts (`aos/brain.md#/Priority and budgets`).
- **`SubagentSlotMissing`.** Cause: your subagent quota is full; nothing was started. Check: `rm` a subagent you no longer need, or say the limit is reached (`aos/agents/subagent.md`).
- **Under WSL, every `.exe` an agent runs (ssh.exe, git.exe, cmd.exe) hangs about 10 s, then fails with `UtilAcceptVsock:273: accept4 failed 110`.** Cause: the root daemon was started in tmux, and the terminal that opened that tmux was closed; the `WSL_INTEROP` the agents inherited (`/run/WSL/<pid>_interop`) is gone. Check: `echo $WSL_INTEROP` and whether that file exists. Fix (a person): `export WSL_INTEROP=/run/WSL/1_interop` in the shell profile, then start the root again. Writing it into the daemon's `.env` does not help (a value the shell exported wins); to rescue one agent, pass it in the `envs` of `subagent add`.

- **A tree with nothing to do still uses CPU.** Cause: every aos-loop runs its body each `interval_ms`, even when there is no work, unless a `gate` skips the run (`aos/cli/parts/loop.md`). Check (a person, read only): `python3 -I $AOS_HOME/py/scripts/idle_cost.py` prints the CPU of each loop of the running tree (`--root` = the root daemon's stack, default `~/aos-home/.stack`; `--seconds` = how long to measure, default 60). Run it while the tree is idle: a body still running at the end is not counted yet.

# The brain

- **A gpt brain fills optional tool parameters it does not need, often with empty strings (for example `index_view` with `"index": ""`), and the tool refuses or answers something else.** Cause: the pack uses `"api": "responses"`, and the installed llm_http is an older one that sends function tools without `"strict": false`; the Responses API then makes every parameter required. Check: `grep -n 'strict=False' $AOS_HOME/lib/tools/base/llm_http/responses_api.py`; no line = the old llm_http, ask a person to run `python3 install.py` in `$AOS_HOME` (`aos/brain.md`).
- **A brain call to a local model service that is not running hangs, then fails with `EndpointFailed` (`retry` true) after about 10 s instead of at once.** Cause: under WSL with mirrored networking, connecting to a port on 127.0.0.1 where nothing listens is not refused at once; it waits until the timeout (about 127 s for a program without one; `::1` is refused at once). Check: whether the service runs; the pack's `connect_timeout_s` sets the wait (default 10; `aos/cli/parts/llm_kernel.md`).

# The overview page (aos-frontend)

- **The page shows `aos-agent ctl ls --json failed`.** Cause: `$AOS_HOME/frontend/bin/aos-frontend` reads the daemon table with `aos-agent ctl ls --json`, run from `/` with the environment the page was started with. Without `AOS_DAEMON` there, or without `aos-agent` on its PATH (the tree's `env.sh` not sourced), the call fails, and the page does not show the command's own error. Check: in the shell that started the page, `echo $AOS_DAEMON` and `command -v aos-agent`; start it again after `source env.sh` with `AOS_DAEMON` set. The systemd unit `$AOS_HOME/frontend/systemd/aos-frontend.service` sets both itself.
