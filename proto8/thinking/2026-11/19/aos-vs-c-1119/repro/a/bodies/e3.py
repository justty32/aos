# e3.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "probe"
SYSTEM = "hi"
std = defs.std
TOOLS = [std.pack("look"), std.tool("base/nonexist")]
LLM = {"model": "fake"}
FSM = std.fsm()
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
