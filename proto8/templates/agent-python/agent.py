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

DESCRIPTION = "Look things up in the workspace and answer by mail."

SYSTEM = """You are an assistant that looks things up in the workspace.
Answer each letter with mailbox_send to its reply_to.
"""

TOOLS = [ag.pack("look"), ag.pack("mailbox"), ag.pack("json")]

LLM = {}                    # {} = the llm kernel's default brain; {"model": "luna"} picks one of its brain packs

FSM = ag.stock_fsm()        # the four cells of the agent-fsm template: idle, think, wait, act

ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
