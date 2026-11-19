# e12b.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "probe"
SYSTEM = "hi"
std = defs.std
TOOLS = [std.pack("look"), std.pack("mailbox")]
LLM = {"model": "no-such-brain"}
FSM = std.fsm()
HOOKS = [std.hooks(), {"timer": {**std.hooks()["timer"], "every_ms": "fast"}}]
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, hooks=HOOKS)
