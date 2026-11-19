# 測 03「auto_restart 連 3 次 3 秒內退＝留 stopped＋reason」與 08「add 剛起的 3 秒內退＝failed to start」；另看退 0 的 auto_restart 字樣。
import sys, time; sys.path.insert(0, __file__.rsplit("/",1)[0])
from importlib import import_module; C = import_module("A-common")
d = C.D("autorestart", {"interval_ms": 50, "procs": {
  "f": {"exec": {"argv": ["sh", "-c", "echo boom >&2; exit 3"]}, "auto_restart": True},
  "z": {"exec": {"argv": ["true"]}, "auto_restart": True},
  "once": {"exec": {"argv": ["sh", "-c", "echo bad >&2; exit 2"]}}}})
d.start(); time.sleep(3)
for n in ("f", "z", "once"):
    r = d.row(n); print(n, r and (r["phase"], r["code"], r["reason"]))
d.shutdown()
import subprocess; print(subprocess.run(["grep", "-c", "\"phase\":\"done\"", str(d.root / "daemon.log")], capture_output=True, text=True).stdout.strip(), "done lines")
