# base2.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "base2"
SYSTEM = "s"
std = defs.std
TOOLS = [std.pack("look"), defs.tool("loc", "mytool")]
LLM = {"model": "fake"}
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, std.fsm())
