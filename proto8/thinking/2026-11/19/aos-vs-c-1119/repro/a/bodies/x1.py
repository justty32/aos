# x1.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "x"
SYSTEM = "s"
std = defs.std
ws = defs.lib("ws", defs.env("AOS_WS", "/lib2"))
TOOLS = [std.pack("look"), ws.pack("p")]
defs.main(DESCRIPTION, SYSTEM, TOOLS, {"model": "fake"}, std.fsm())
