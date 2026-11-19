# 測：daemon 被 kill -9 後，在寫不了的 stack（唯讀）上再起＝第一份窗寫不了→退 1，途中把接回的子項全 SIGTERM；之後 stack 好了再起，信加的列不見了（只有 daemon.json 的回來）。
import sys, time, os, subprocess, json; sys.path.insert(0, __file__.rsplit("/",1)[0])
from importlib import import_module; C = import_module("A-common")
d = C.D("rorestart", {"interval_ms": 50, "procs": {"a": {"exec": {"argv": ["sleep", "1000"]}, "interval_ms": 0}}})
d.start()
subprocess.run(["aos-daemon-ctl", "-d", str(d.stack), "add", "--name", "b", str(d.root / "bdef")], capture_output=True, text=True) if False else None
# 信加 b（loop 型）
C.write(d.root / "b.json", {"procs_added": {"b": {"exec": {"argv": ["sleep", "1000"]}, "interval_ms": 0}}})
r = subprocess.run("aos-post send %s < %s" % (d.stack / "procs_requests", d.root / "b.json"), shell=True, capture_output=True, text=True); print("send", r.returncode, r.stderr.strip())
time.sleep(1.5); pids = {n: x["pid"] for n, x in d.rows().items()}; print("before", {n: x["phase"] for n, x in d.rows().items()}, pids)
d.kill9()
os.chmod(d.stack, 0o555)
d.p = subprocess.Popen(["aos-daemon", str(d.cfg)], cwd=d.root, env=dict(os.environ, AOS_STACK=str(d.stack)), stderr=subprocess.PIPE, text=True)
try:
    out = d.p.communicate(timeout=30)[1]; print("ro daemon rc", d.p.returncode, out.strip()[:400])
finally:
    os.chmod(d.stack, 0o755)
print("children alive after ro run:", {n: os.path.exists(f"/proc/{p}") for n, p in pids.items()})
d.start(); time.sleep(1.5)
print("after restart rows", {n: x["phase"] for n, x in d.rows().items()})
d.shutdown()
for n, p in pids.items():
    if os.path.exists(f"/proc/{p}"): C.kill_mine(p, d.root); print("killed leftover", n)
