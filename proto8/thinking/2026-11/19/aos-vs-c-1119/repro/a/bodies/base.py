# base.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "base"
SYSTEM = "base system v1"
std = defs.std
lib2 = defs.lib("lib2", "/home/guanyu/.aos/scratch/aos-vs-c-1119/probe-a/lib2")
TOOLS = [std.pack("look"), lib2.pack("p")]
LLM = {"model": "fake"}
FSM = std.fsm()
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
