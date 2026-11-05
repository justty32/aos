# Other agents

Tool `agents`: start a child agent from a definition, talk to it, remove it, list every agent on your daemon.

A child agent runs on the same daemon as you, from a definition folder you name. It does not inherit your brain or your tools; give them explicitly if it needs them.

Calls:

- start one: `{"op": "add", "name": "kid", "def": "agents/kid"}`. Options: `"endpoint": "fake"` (which brain pack it uses), `"tools": [{"name": "clock", "path": "tools/clock"}]`, `"ws": "kid_ws"` (default: your own workspace, shared files), `"limits": {"mem_mb": 512}`.
- send a message and return at once: `{"op": "say", "name": "kid", "text": "..."}`
- send and wait for the answer: `{"op": "ask", "name": "kid", "text": "...", "timeout_s": 120}` (default 600)
- remove it (its stack is deleted): `{"op": "rm", "name": "kid"}`
- list all agents on the daemon: `{"op": "ls"}` (one line of JSON: name, phase, ws, queue size, reason)

Rules:

- `def` is relative to your workspace, or an absolute path inside the repo's `proto8/lib/` or `proto8/demo/`. The folder must declare `aos-agent` in its `interfaces.json`; otherwise `InterfaceMissing`.
- `say`, `ask`, `rm` work only on agents you started yourself. Others give `ChildUnknown`. You may `ls` everyone.
- How many agents may run is decided by the kernel (judge), not by you. `AddRejected ... SlotMissing` means the limit is reached: remove a child you no longer need, or report that the limit is reached. Do not retry in a loop.
- `AnswerMissing` after `ask`: the child did not answer within `timeout_s`. Check its row with `ls`: if its phase is `stopped` with a `reason`, it crashed (see node `status`); if it is `running`, it is just slow, ask again with a longer timeout or `say` and come back later.
- Remove children when you are done with them. Nobody removes them for you.
