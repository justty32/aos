#!/usr/bin/env python3
"""tool-python 骨架 - 最小、合格、能跑的工具：把兩個數相加。抄出去改 @fn.tool 底下那個函數（名字、docstring、參數、內容）就是新工具（說明看 README.md）。"""
# ---- setup: find the aos package (keep these lines as they are) ----
import os, sys
sys.dont_write_bytecode = True
_d = os.path.dirname(os.path.realpath(__file__))
_found = [_d]
if os.environ.get("AOS_HOME"):
    _found.append(os.path.join(os.environ["AOS_HOME"], "lib"))
sys.path[:0] = _found
try:
    from aos.py import fn
except ModuleNotFoundError as _e:
    if _e.name != "aos":
        raise
    if os.environ.get("AOS_HOME"):
        _line = "%s: error: ModuleMissing %s not found (under $AOS_HOME/lib, or next to tool.py)\n" % (os.path.basename(_found[0]), _e.name)
    else:
        _line = "%s: error: HomeMissing AOS_HOME is not set (set it, or copy the %s package folder next to tool.py)\n" % (os.path.basename(_found[0]), _e.name)
    sys.stderr.write(_line)
    sys.stdout.write(_line)
    sys.exit(1)
# ---- your tool: change the lines below ----


@fn.tool(meta={"side_effect": False})
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5

    Args:
      a: the first number
      b: the second number
    """
    return a + b


fn.main(add)
