# e6b.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "probe"
SYSTEM = "hi"
std = defs.std
TOOLS = [std.pack("look")]
LLM = {"model": "fake"}
FSM = defs.fsm(std.fsm(), [defs.state("act", timeout_ms="5")])
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
