#!/usr/bin/env python3
"""agent-python 骨架 - 一支 agent.py 宣告一隻 agent（說明、system、工具、腦設定、狀態機），python3 agent.py --compile 編譯成這夾的定義檔（說明看 README.md）。"""
# ---- setup: find the aos package (keep these lines as they are) ----
import os, sys
sys.dont_write_bytecode = True
_d = os.path.dirname(os.path.realpath(__file__))
_found = [_d]
if os.environ.get("AOS_HOME"):
    _found.insert(0, os.path.join(os.environ["AOS_HOME"], "lib"))   # $AOS_HOME/lib first: an aos.py next to agent.py must not win
sys.path[:0] = _found
try:
    from aos.py.agent import defs
except ModuleNotFoundError as _e:
    if _e.name != "aos" and not (_e.name or "").startswith("aos."):
        raise
    if os.environ.get("AOS_HOME"):
        _line = "%s: error: ModuleMissing %s not found (under $AOS_HOME/lib, or next to agent.py)\n" % (os.path.basename(_d), _e.name)
    else:
        _line = "%s: error: HomeMissing AOS_HOME is not set (set it, or copy the %s package folder next to agent.py)\n" % (os.path.basename(_d), _e.name)
    sys.stderr.write(_line)
    sys.exit(1)
# ---- your agent: change the lines below ----

std = defs.std              # the library that comes with aos; another one: my = defs.lib("my", defs.env("AOS_WS", "/lib/my"))

agent = defs.Agent(
    "Look things up in the workspace and answer by mail.",     # one sentence: what the agent does
    system="""You are an assistant that looks things up in the workspace.
Answer each letter with mailbox_send to its reply_to.
""",
    tools=[std.pack("look"), std.pack("mailbox"), std.pack("json")],   # copied into tools.json tool by tool
    llm={},                 # {} = the llm kernel's default brain; {"model": "luna"} picks one of its brain packs
    fsm=std.fsm(),          # the four cells of the agent-fsm template: idle, think, wait, act
    hooks={},               # no hooks yet, but declared, so breakpoints (aos-gdb) and aos-agent hook work; std.hooks() = the agent-fsm template's hooks
)

defs.main(agent)
