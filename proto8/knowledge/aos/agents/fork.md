# fork: a copy of you, one goal, just the conclusion

Tool `fork` copies you as you are now into a fork on your daemon: your definition, the settings you changed in your stack (tools, llm, hooks, system) and your whole conversation. The fork gets one goal; you get back only its short conclusion, as the result of the call. The fork's steps do not enter your history. Only for agent-fsm bodies (a Claude or Codex agent gets `BodyUnsupported`: use `subagent`).

`fork` or `subagent`?

- `fork`: a side task that needs what you already know. One answer back; the fork is then removed.
- `subagent`: a helper from another definition that you keep talking to; it knows only what you tell it.

Call: `{"goal": "Check the three config files we discussed for the port setting and return the values"}`. Say in `goal` what to bring back (at most `max_chars`, default 600).

More: `aos/agents/fork.md#/fork: what is copied` (what is copied, what the fork sees), `aos/agents/fork.md#/fork: waiting, depth, keep, errors` (waiting, depth, keep, errors).

# fork: what is copied

- Copied: your definition (the same folder), your conversation, and your own copies of tools, llm, hooks and system (what `self_tools`, `self_llm`, `self_hook`, `self_system` changed). Your definition must declare `history` in its `interfaces.json` (else `HistoryMissing`).
- Not copied: your goal, your to-do list, the records of your tools (subagents, kept helpers), your queue and mailbox. The fork's hooks start fresh.
- The fork's conversation ends with your fork call. Its result there says it is the copy; any later calls of that same turn say they were not run. Then one message: you are a fork, your task (the goal), reply with the conclusion only, you cannot fork again.
- Only for agents with an agent-fsm body. A Claude or Codex agent calling `fork` gets `BodyUnsupported`: to hand work to another agent, use `subagent`.
- What the fork changes (files in the workspace aside) stays in the fork.

# fork: waiting, depth, keep, errors

- Waiting: up to `timeout_s` seconds (default 0 = no limit), or `timeout_cycles` clock cycles instead (a positive integer). Both = `ArgumentsBad`.
- Depth: one level only (`AOS_FORK_DEPTH`): a fork calling `fork` gets `DepthExceeded`; it should do the step itself.
- `keep: true`: the fork is stopped, not removed, and the answer gets a last line `details: <its stack>/`. To ask it more, a human runs `aos-agent ctl start --target <name>`, then `say` / `listen`.
- `AnswerMissing`: no answer in time; the error line ends with `(details: <its stack>/)` and the fork is stopped, kept for a human.
- `ArgumentsBad`: `goal` missing, a bad value, or a key fork does not take (`from`, `tools`, `model`: use `subagent`). `HistoryMissing`, `InterfaceMissing`, `InterfaceBad`, `DefMissing`: your definition cannot be copied. `BodyUnsupported`: not an agent-fsm body; use `subagent`.
- `DaemonMissing`, `DaemonFailed`: do the step yourself; try at most once more later (`aos/errors/common.md`).
