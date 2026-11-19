# e1.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
DESCRIPTION = "probe"
SYSTEM = "hi"
std = defs.std
TOOLS = [std.pack("look")]
LLM = {"model": "fake"}
def cell(n): return ["python3", defs.home("/templates/agent-fsm/%s.py" % n)]
FSM = defs.fsm("idle", [
    defs.state("idle", cell("idle"), {0: "think", 10: "idle"}),
    defs.state("think", cell("brain"), {0: "wiat", 10: "idle"}),
    defs.state("wait", cell("wait"), {0: "act", 10: "wait", 11: "think"}),
    defs.state("act", cell("act"), {0: "think", 10: "idle"}, timeout_ms=0),
])
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
