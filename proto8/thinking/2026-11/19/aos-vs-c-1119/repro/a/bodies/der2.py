# der2.py: one agent.py body (the part under "# ---- your agent") that probe-a mk.sh puts into a copy of agent-python (aos-vs-c-1119).
base = defs.load("../base2")
defs.main("der2", base.SYSTEM, [base.TOOLS], base.LLM, base.FSM)
