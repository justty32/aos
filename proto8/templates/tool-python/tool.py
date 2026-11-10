#!/usr/bin/env python3
"""tool-python 骨架 - 最小、合格、能跑的工具：把兩個數相加。抄出去改 DESCRIPTION、PARAMS、run 就是新工具（說明看 README.md）。"""
# ---- setup: find tool_spec.py (keep these lines as they are) ----
import os, sys
sys.dont_write_bytecode = True
_d = os.path.dirname(os.path.realpath(__file__))
_found, _up = [_d], _d
while _up != os.path.dirname(_up):
    _up = os.path.dirname(_up)
    if os.path.isfile(os.path.join(_up, "lib", "tool_spec.py")):
        _found.append(os.path.join(_up, "lib"))
        break
if os.environ.get("AOS_HOME"):
    _found.append(os.path.join(os.environ["AOS_HOME"], "lib"))
sys.path[:0] = _found
try:
    import tool_spec as ts
except ModuleNotFoundError as _e:
    if _e.name not in ("tool_spec", "tool_io"):
        raise
    _line = "%s: error: ModuleMissing %s.py not found (set AOS_HOME, or copy it next to tool.py)\n" % (os.path.basename(_found[0]), _e.name)
    sys.stderr.write(_line)
    sys.stdout.write(_line)
    sys.exit(1)
# ---- your tool: change the lines below ----

DESCRIPTION = 'Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5'

PARAMS = [
    ts.param("a", "number", "the first number"),
    ts.param("b", "number", "the second number"),
]

META = {"side_effect": False}


def run(args):
    return args["a"] + args["b"]


ts.main(run, DESCRIPTION, PARAMS, META)
