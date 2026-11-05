# Other agents

Tool `agents`: start a child agent, talk to it, remove it, list every agent on your daemon.

A child agent runs on the same daemon as you. It does not inherit your brain or your tools; give them explicitly if it needs them.

Two ways to start one:

- from an existing definition: `{"op": "add", "name": "kid", "def": "agents/kid"}`. Options change only this child (they go to its own stack, the definition stays as it is): `"llm": {"endpoint": "fake"}` (which brain pack it uses), `"tools": [{"name": "clock", "path": "tools/clock"}]`, `"tools_rm": ["self_tools"]`.
- by writing a new definition: `{"op": "new", "name": "kid", "path": "defs/kid", "from": "agents/kid", "files": {"system.txt": "You are ..."}}`. `from` is copied to `path` (inside your workspace, must not exist yet), then `files` (full text per file), `llm`, `tools`, `tools_rm` are written into the copy. Without `from`, `files` must hold the whole definition. The folder stays; start it again later with `add` and `"def": "defs/kid"`.

Both take `"ws": "kid_ws"` (the child's workspace: relative to yours, or absolute; default: your own workspace, shared files) and `"limits": {"mem_mb": 512}`.

Other calls:

- send a message and return at once: `{"op": "say", "name": "kid", "text": "..."}`
- send and wait for the answer: `{"op": "ask", "name": "kid", "text": "...", "timeout_s": 120}` (default 600)
- remove it (its stack is deleted): `{"op": "rm", "name": "kid"}`
- list: `{"op": "ls"}` (one line of JSON: `agents` = the daemon table, `children` = yours, `max_children`)

Rules:

- `def` and `from` are relative to your workspace, or absolute. The folder must declare `aos-agent` in its `interfaces.json`; otherwise `InterfaceMissing`.
- `say`, `ask`, `rm` work only on agents you started yourself. Others give `ChildUnknown`; a child removed by someone else gives `ChildMissing` once and is then forgotten. You may `ls` everyone.
- Two limits. Your own: at most `max_children` children at once (default 4); over it `add` / `new` fail with `ChildSlotMissing` and nothing is started. The daemon's: the judge counts every agent on the daemon; `AddRejected ... SlotMissing` means the daemon is full. Either way remove a child you no longer need, or report that the limit is reached. Do not retry in a loop.
- `AnswerMissing` after `ask`: the child did not answer within `timeout_s`. Check its row with `ls`: if its phase is `stopped` with a `reason`, it crashed (see node `status`); if it is `running`, it is just slow, ask again with a longer timeout or `say` and come back later.
- Remove children when you are done with them. Nobody removes them for you.
