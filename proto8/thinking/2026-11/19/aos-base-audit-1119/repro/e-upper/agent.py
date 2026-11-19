#!/usr/bin/env python3
"""agent-python 骨架 - 一支 agent.py 宣告一隻 agent（說明、system、工具、腦設定、狀態機），python3 agent.py --write-defs 生出這夾的定義檔（說明看 README.md）。"""
# ---- setup: find the aos package (keep these lines as they are) ----
import os, sys
sys.dont_write_bytecode = True
_d = os.path.dirname(os.path.realpath(__file__))
_found = [_d]
if os.environ.get("AOS_HOME"):
    _found.append(os.path.join(os.environ["AOS_HOME"], "lib"))
sys.path[:0] = _found
try:
    from aos import agent_spec as ag
except ModuleNotFoundError as _e:
    if _e.name != "aos":
        raise
    if os.environ.get("AOS_HOME"):
        _line = "%s: error: ModuleMissing %s not found (under $AOS_HOME/lib, or next to agent.py)\n" % (os.path.basename(_found[0]), _e.name)
    else:
        _line = "%s: error: HomeMissing AOS_HOME is not set (set it, or copy the %s package folder next to agent.py)\n" % (os.path.basename(_found[0]), _e.name)
    sys.stderr.write(_line)
    sys.exit(1)
# ---- your agent: change the lines below ----
# e-upper 實驗用：版本由環境變數 MARK（A/B）、FSMV（std/renamed）、BIG（system 放大倍數）決定
MARK = os.environ.get("MARK", "A")
DESCRIPTION = "e-upper test agent version " + MARK
SYSTEM = ("SYSTEM-VERSION-" + MARK + "\n") * int(os.environ.get("BIG", "1"))
std = ag.std
if os.environ.get("SYSFILE"):
    SYSTEM = ag.by_hand(os.environ["SYSFILE"])
if MARK == "A":
    TOOLS = [std.pack("gadgets"), std.pack("mailbox")]
else:
    TOOLS = [std.pack("mailbox"), std.pack("look")]
LLM = {"model": "fake", "temperature": 0.1 if MARK == "A" else 0.9}
def _cell(n):
    return ["python3", ag.home("/templates/agent-fsm/%s.py" % n)]
if os.environ.get("FSMV") == "renamed":
    FSM = ag.fsm("rest", [ag.state("rest", _cell("idle"), {0: "think", 10: "rest"}),
                          ag.state("think", _cell("brain"), {0: "wait", 10: "rest"}),
                          ag.state("wait", _cell("wait"), {0: "act", 10: "wait", 11: "think"}),
                          ag.state("act", _cell("act"), {0: "think", 10: "rest"}, timeout_ms=0)])
else:
    FSM = std.fsm()
ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, hooks=std.hooks() if os.environ.get("HOOKS") else None)
