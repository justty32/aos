# derived.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
base = defs.load("../base")
DESCRIPTION = "derived"
defs.main(DESCRIPTION, base.SYSTEM + "more\n", [base.TOOLS], base.LLM, base.FSM)
