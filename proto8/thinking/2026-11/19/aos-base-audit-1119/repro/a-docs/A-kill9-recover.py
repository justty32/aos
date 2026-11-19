# 測 08:9／08:11：daemon kill -9 後（模擬「fork 了、表還沒寫」＝把 procs_state.json 拿掉）再起，loop 型與 exec 型各會不會在同一格多起一份。
import sys, time, os, subprocess; sys.path.insert(0, __file__.rsplit("/",1)[0])
from importlib import import_module; C = import_module("A-common")
d = C.D("kill9", {"interval_ms": 50, "procs": {
  "lp": {"exec": {"argv": ["sleep", "1000"]}, "interval_ms": 0},
  "ex": {"exec": {"argv": ["sleep", "1000"]}}}})
d.start(); time.sleep(1.5)
before = {n: r["pid"] for n, r in d.rows().items()}; print("before", before)
lp_kids = subprocess.run(["pgrep", "-P", str(before["lp"])], capture_output=True, text=True).stdout.split()
d.kill9(); os.rename(d.stack / "procs_state.json", d.stack / "procs_state.json.hidden")
d.start(); time.sleep(1.5)
after = {n: r["pid"] for n, r in d.rows().items()}; print("after", after)
for n in before:
    alive = os.path.exists(f"/proc/{before[n]}")
    print(n, "old pid alive:", alive, "same row pid:", after.get(n) == before[n])
d.shutdown()
for n, p in before.items():
    if os.path.exists(f"/proc/{p}"):
        print("leftover", n, p); C.kill_mine(p, d.root)
for k in lp_kids:
    if os.path.exists(f"/proc/{k}"):
        try: C.kill_mine(int(k), d.root); print("leftover lp body", k)
        except Exception as e: print("skip", k, e)
