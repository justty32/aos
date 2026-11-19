# 測：daemon 自己的身體（exec）跑的期間，表上的子項沒人照顧（退了不記、stop 不送）——文件只寫 poke 不打斷（08:36），沒寫照顧也停。
import sys, time; sys.path.insert(0, __file__.rsplit("/",1)[0])
from importlib import import_module; C = import_module("A-common")
d = C.D("bodyblocks", {"interval_ms": 50, "exec": {"argv": ["sleep", "6"]},
  "procs": {"x": {"exec": {"argv": ["sh", "-c", "sleep 1; exit 3"]}}}})
d.start(); t0 = time.time()
while time.time() - t0 < 12:
    r = d.row("x"); print("%.1f" % (time.time() - t0), r and r["phase"], r and r["code"]); 
    if r and r["phase"] == "stopped": break
    time.sleep(1)
d.shutdown()
