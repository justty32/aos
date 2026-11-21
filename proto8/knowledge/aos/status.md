# Reading state

The daemon table, the phases an agent can be in, and what each phase means for you.

Every daemon keeps one table, one row per proc: `name  phase  ws  queue N  [reason ...]`. Tools and commands that show it: the tool `agents_ctl` with `{"op": "ls"}` (the whole table; `subagent` `{"op": "ls"}` lists only yours); for humans `aos-agent ctl ls` and `aos-agent ctl state --target <name>`.

Phases:

| phase | meaning | what to do |
|---|---|---|
| `running` | alive; answers letters in its queue | talk to it (`say` / `ask`) |
| `stopped` | not running; stack kept. Either a human stopped it, or it crashed: then the row has a `reason` with the error line that killed it | read the `reason`; fix the cause (often a bad tool or brain setting), then a human runs `aos-agent ctl start --target <name>`. Letters you send are kept, not answered |
| `sleeping` | the daemon put it to sleep (daemon shutting down, or `sleep` command); it wakes when the daemon comes back or on `wake` | wait, or ask a human |
| `stopping` | finishing its current turn before stopping | wait |
| `stuck` | alive, but it has not answered a control request (stop, pause ...) in time: only when the row sets `stuck_after_cycles` / `stuck_after_ms` (not set or 0 = never stuck). The `reason` reads `control window has not been answered within N cycles`. Usually one long step, or a hung body. It turns back to `running` as soon as it answers. The daemon only marks it, unless the row has `restart_on_stuck`: then it is restarted, and stopped after 3 tries with no answer | wait; commands treat it as `running`. If it stays stuck, tell a human (they can `sleep` or `rm` it) |

A row that disappeared: the proc finished (exit 0) or was removed (`rm`). `rm` keeps its stack (only `rm` with purge deletes it); adding it again with the same stack picks it up. After `ask` a missing row shows as `InstanceMissing`.

`queue N`: how many letters wait in its queue. `queue 0` with phase `running` means idle.

Reading a `reason`: it is the last error line of the thing that died, in the usual form `program: error: Code reason`. Example: `agent-fsm: error: LlmKernelMissing AOS_LLM_KERNEL is not set` means the agent could not reach the llm kernel; a human must set it up. See `aos/errors.md` for codes.

Quiet for a long time: while an agent is in a long turn (an eca CLI turn, or agent-fsm waiting for its brain) and nothing has moved for 10 minutes, its stack has `quiet.json` (`{"quiet": true, "what": "cli_turn" | "brain_reply", "since", "at", "quiet_s", "pid"}`). It is only a mark: nothing is killed, no letter is dropped, and the phase stays `running`. It goes away when the turn moves again or ends; if its `pid` is gone the file is stale. A long turn is not a crash: there is no time limit unless the definition sets one.

Paused: a human can pause and resume an agent (`aos-agent ctl pause/resume`). A paused agent still shows `running` in the daemon table; it just does not take the next step. If an `ask` to a subagent hangs with no `reason`, it may be paused; a human has to resume it.
