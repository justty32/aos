#!/usr/bin/env python3
"""kernel-python 骨架 - 一支 kernel.py 宣告一個 kernel（說明、kernel.json 的鍵、hook、身體），python3 kernel.py --compile 編譯成這夾的定義檔（說明看 README.md）。"""
# ---- setup: find the aos package (keep these lines as they are) ----
import os, sys
sys.dont_write_bytecode = True
_d = os.path.dirname(os.path.realpath(__file__))
_found = [_d]
if os.environ.get("AOS_HOME"):
    _found.insert(0, os.path.join(os.environ["AOS_HOME"], "lib"))   # $AOS_HOME/lib first: an aos.py next to kernel.py must not win
sys.path[:0] = _found
try:
    from aos.py.kernel import defs
except ModuleNotFoundError as _e:
    if _e.name != "aos" and not (_e.name or "").startswith("aos."):
        raise
    if os.environ.get("AOS_HOME"):
        _line = "%s: error: ModuleMissing %s not found (under $AOS_HOME/lib, or next to kernel.py)\n" % (os.path.basename(_d), _e.name)
    else:
        _line = "%s: error: HomeMissing AOS_HOME is not set (set it, or copy the %s package folder next to kernel.py)\n" % (os.path.basename(_d), _e.name)
    sys.stderr.write(_line)
    sys.exit(1)
# ---- your kernel: change the lines below ----

kernel = defs.Kernel(
    "Pass every request on to the daemon, managing nothing yet.",   # one sentence: what the kernel does
    knobs={},               # the keys of kernel.json; {} = manage nothing. Examples: {"allowed": ["ann"], "max_running": 2, "queue": True}
    program="kernel",       # "kernel" = the station that admits procs; "kernel_llm" = the llm kernel
    body=defs.loop(),       # one row of a daemon (aos-loop, every 300 ms); defs.daemon() = a daemon of its own
)

defs.main(kernel)
