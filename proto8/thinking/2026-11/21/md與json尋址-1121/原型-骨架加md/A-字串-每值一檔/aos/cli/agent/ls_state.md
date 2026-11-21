# ctl ls and ctl state

```sh
aos-agent ctl ls                 # NAME STATE WORKSPACE QUEUED REASON (TAB-separated)
aos-agent ctl ls -l              # + QUEUE RESTARTS COOLDOWN LAST ERROR
aos-agent ctl state -t bob       # one line per part
aos-agent ctl state -t bob tools history   # only these parts, in full
```

An empty table prints nothing. `-j` prints JSON. `state` (alias `status`) has the parts who, state, tools, llm, system, hooks, history, mailbox, subagents, resources, time; give part names for detail, or `all`. `state tools` lists every tool and ends with `own: N listed, M set to null (...)` when the agent changed its tools.
