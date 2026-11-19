# e7.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "probe"
SYSTEM = "hi"
std = defs.std
my = defs.lib("my", "/home/guanyu/.aos/scratch/aos-vs-c-1119/probe-a/lib1")
UNUSED = std.pack("shell")
TOOLS = [std.pack("look"), defs.tool("ghost2", "relative/not/there")]
LLM = {"model": "fake"}
FSM = defs.fsm("idle", [defs.state("idle", ["python3", "nocell.py"], {0: "idle"}), defs.state("orphan", ["true"], {0: "orphan"})])
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
