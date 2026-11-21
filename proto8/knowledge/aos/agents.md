# Other agents: which tool

- A helper you can talk to, change and remove later: `subagent` (see `aos/agents/subagent.md`).
- Start, stop or list any agent on the daemon, without making it yours: `agents_ctl` (see `aos/agents.md#/Any agent on the table: agents_ctl`).
- A side task that needs what you already know, only the conclusion back: `fork` (agent-fsm only; see `aos/agents/fork.md`). These three come in the `subagent` pack, which no stock template has (agent-fsm or eca); an eca uses the helpers built into its own CLI. A definition may add the pack (see `aos/packs.json`); on an eca you then have subagent and agents_ctl (fork still refuses an eca body with `BodyUnsupported`). `self_state` with part `tools` shows what you have.
- A new kind of agent: copy a template with `agent_def` (pack def: eca has it, agent-fsm only when its definition adds it), edit the copy with your file tools, then start it with `subagent` (see `aos/agents.md#/New definitions: agent_def`).

A subagent runs on the same daemon as you. It does not inherit your brain or your tools: they come from its own definition.

# Any agent on the table: agents_ctl

Tool `agents_ctl` is `aos-agent ctl` for any agent on your daemon table, not only yours. It keeps no record and has no quota; whether a call works is up to your permissions and the daemon. It cannot talk to an agent or change its tools or brain: for that, start the agent with `subagent`.

One op per call (the keys are the ctl flags):

- `{"op": "ls"}` (one line per agent: NAME STATE WORKSPACE QUEUED REASON; `"long": true` adds health columns; `"json": true` = every field as JSON)
- `{"op": "state", "name": "worker"}`
- `{"op": "add", "def": "defs/helper", "name": "worker", "ws": "work"}` (same keys as `subagent` add, `aos/agents/subagent.md#/subagent add: more options`; the agent is not yours afterwards)
- `{"op": "stop", "name": "worker"}` (after this round; `start` = run again)
- `{"op": "sleep", "name": "worker"}` (now; `wake` = back); `pause` / `resume` = hold / go on
- `{"op": "rm", "name": "worker"}` (keeps its stack; `"purge": true` deletes it)
- `{"op": "stop", "name": "<you>", "no_wait": true}` (stop yourself: returns once the daemon, or the kernel in front of it, has taken the request; you stop when this step ends. `no_wait` works for `stop`, `sleep`, `pause` and `rm`; without it, stopping yourself waits for this very step to end and runs into `timeout_s`)
- `{"op": "where", "name": "worker", "what": "ws"}` (its workspace; default: its stack)
- `{"op": "who"}` (which agent you are)

Rules:

- Relative paths start at your workspace.
- It works on agents that are not yours too, `rm` included, as far as your permissions go. If you remove one of your own subagents here, `subagent` forgets it on its next call and the slot frees.
- `InstanceMissing`: no such name on the table; `ls` first. `InstanceExists`: the name is taken; pick another. `AddRejected`: the daemon refused, often because it is full. `InterfaceMissing`: that folder is not an agent definition (its `interfaces.json` declares no `aos-agent`). `PhaseBad`: wrong phase for that op (for example `start` on a sleeping agent: use `wake`); run `state` first. `DaemonMissing`: you do not run under a daemon; say so.
- When `$AOS_KERNEL` is set, stop, sleep, start and wake go through that kernel first. If it refuses, the error line is `CtlRejected` and the kernel's own code and reason follow in the message (for example `CtlRejected the stop letter was refused: HoldRefused <reason>`). A refusal is a decision: read the reason, do not just send the same request again.

# New definitions: agent_def

Tool `agent_def` makes agent definitions. A definition is a folder (`system.txt`, `tools.json`, `llm.json`, `interfaces.json`, ...; what each file does: `aos/definition.md`); a new kind of agent = a copy of a template, edited.

One op per call:

- copy a stock template: `{"op": "new", "template": "agent-fsm", "path": "defs/helper"}` (`template` = the name of a folder under `$AOS_HOME/templates`; stock agent templates: `agent-fsm`, `eca-claude`, `eca-pi`, `reviewer`; a wrong name is `DefMissing` and the reason lists the templates there)
- copy any other definition folder: `{"op": "new", "from": "defs/helper", "path": "defs/helper2"}`
- check: `{"op": "check", "path": "defs/helper"}` (prints `{"problems": [...]}`; an empty list = OK. A link in the folder that points to nothing (a moved or deleted `defs.extern` target) is one problem, and the other checks of that definition wait until it is fixed. Besides the files it checks that every tool path and every program the states, loop and hooks run exist, and that brain settings have the right types (`temperature: "hot"` is a problem); what it could not check here, like a variable that is not set, comes in `"warnings"`. It does not check the model name. Compiling with `agent.py --compile` checks none of this: run check after compiling)
- change its tools: `{"op": "tools", "path": "defs/helper", "args": {"op": "add", "path": "tools/math"}}` (`args` = what `self_tools` takes: ls, get, add, rm)
- change its brain settings: `{"op": "llm", "path": "defs/helper", "args": {"op": "set", "settings": {"model": "fake"}}}` (`args` = what `self_llm` takes: ls, set, rm)
- change its system text: `{"op": "system", "path": "defs/helper", "args": {"op": "set", "text": "You are ..."}}` (`args` = what `self_system` takes: get, set)

Steps:

1. `new` from a template.
2. Edit the copy with ops `tools` / `llm` / `system` (there is no reset), or with your normal file tools: `system.txt` (who it is), `tools.json` (its tools), `llm.json` (its brain, like `{"model": "fake"}`).
3. `check` it.
4. Start it: `subagent` `{"op": "add", "def": "defs/helper", "name": "helper"}` (yours), or `agents_ctl` add (not yours).

Rules:

- `new` only copies and starts nothing. The copy is the folder as it is, like `cp -r`: no path inside it is changed. `_metainfo.json` is copied too, untouched. So a relative path to a file inside the folder (`fn/add.py`) means the copy's own file; one that leads out of the folder (`../shared/x`) now starts from the new place and may point somewhere else.
- `path` must not exist yet; it can be anywhere you may write. Relative paths start at your workspace.
- `DefExists`: pick another `path`. `DefMissing`: the folder (`from`, or `path` for check) is not there. `DirectiveBad`: the `{"$env": ...}` could not be resolved (the variable is not set). `DefBad`: check found problems; fix the files it names and check again.
- Editing a definition affects every agent that uses it. To change only one agent, use `subagent` tools / llm on your subagent, or `self_tools` / `self_llm` on yourself.
