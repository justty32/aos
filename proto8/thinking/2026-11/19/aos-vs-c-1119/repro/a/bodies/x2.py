# x2.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "eca probe"
SYSTEM = "s"
std = defs.std
TOOLS = [std.pack("look")]
defs.main(DESCRIPTION, SYSTEM, TOOLS, {"model": "luna", "temperature": 0.2})
