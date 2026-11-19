# e10.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "probe"
SYSTEM = "hi"
std = defs.std
base = defs.load("../nobase")
defs.main(DESCRIPTION, SYSTEM, base.TOOLS, {}, std.fsm())
