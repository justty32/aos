# v1.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "v"
SYSTEM = "s"
std = defs.std
lib2 = defs.lib("lib2", "/home/guanyu/.aos/scratch/aos-vs-c-1119/probe-a/lib2")
TOOLS = [std.pack("look"), lib2.tool("t2")]
defs.main(DESCRIPTION, SYSTEM, TOOLS, {"model": "fake"}, std.fsm(), files={"loop.json": {"interval_ms": 50}})
