# Reading state

The daemon table, the phases an agent can be in, and what each phase means for you.

Every daemon keeps one table, one row per proc: `name  phase  ws  queue N  [reason ...]`. Tools and commands that show it: the tool `agents` with `{"op": "ls"}`; for humans `aos-agent ctl ls` and `aos-agent ctl state --target <name>`.

Phases:

| phase | meaning | what to do |
|---|---|---|
| `running` | alive; answers letters in its queue | talk to it (`say` / `ask`) |
| `stopped` | not running; stack kept. Either a human stopped it, or it crashed: then the row has a `reason` with the error line that killed it | read the `reason`; fix the cause (often a bad tool or brain setting), then a human runs `aos-agent ctl start --target <name>`. Letters you send are kept, not answered |
| `sleeping` | the daemon put it to sleep (daemon shutting down, or `sleep` command); it wakes when the daemon comes back or on `wake` | wait, or ask a human |
| `stopping` | finishing its current turn before stopping | wait |

A row that disappeared: the proc finished (exit 0) or was removed (`rm`). Its stack is gone after `rm`; after `ask` this shows as `InstanceMissing`.

`queue N`: how many letters wait in its queue. `queue 0` with phase `running` means idle.

Reading a `reason`: it is the last error line of the thing that died, in the usual form `program: error: Code reason`. Example: `agent-fsm: error: LlmKernelMissing AOS_LLM_KERNEL is not set` means the agent could not reach the llm kernel; a human must set it up. See node `errors` for codes.

Paused: a human can pause and resume an agent (`aos-agent ctl pause/resume`). A paused agent still shows `running` in the daemon table; it just does not take the next step. If an `ask` to a child hangs with no `reason`, it may be paused; a human has to resume it.
