# e4.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "probe"
SYSTEM = "hi"
std = defs.std
my = defs.lib("my", "/home/guanyu/.aos/scratch/aos-vs-c-1119/probe-a/lib1")
TOOLS = [std.pack("look"), my.pack("look", prefix="")]
LLM = {"model": "fake"}
FSM = std.fsm()
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
