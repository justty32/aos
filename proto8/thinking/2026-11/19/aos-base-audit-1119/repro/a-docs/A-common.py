# 共用：在 a-docs/forkA/<名字>/ 起一台只帶 stack 的暫存 daemon（只認自己記的 pid）。
import json, os, signal, subprocess, time
from pathlib import Path
BASE = Path.home() / ".aos/scratch/aos-base-audit-1119/a-docs/forkA"
def write(p, v):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name("." + p.name); t.write_text(json.dumps(v) + "\n"); t.replace(p)
def read(p):
    try: return json.loads(Path(p).read_text())
    except Exception: return None
class D:
    def __init__(self, name, cfg):
        self.root = BASE / name
        if self.root.exists():
            subprocess.run(["rm", "-rf", str(self.root)])
        self.root.mkdir(parents=True)
        self.stack = self.root / "stack"
        self.cfg = self.root / "daemon.json"
        write(self.cfg, cfg)
        self.p = None
    def start(self):
        env = dict(os.environ, AOS_STACK=str(self.stack))
        self.out = open(self.root / "daemon.log", "a"); self.err = open(self.root / "daemon.err", "a")
        self.p = subprocess.Popen(["aos-daemon", "--enable-logs", str(self.cfg)], cwd=self.root, env=env, stdout=self.out, stderr=self.err)
        print("daemon pid", self.p.pid)
        for _ in range(200):
            s = read(self.stack / "procs_state.json")
            if isinstance(s, dict) and s.get("pid") == self.p.pid: return
            time.sleep(.05)
        raise SystemExit("daemon did not come up")
    def rows(self):
        s = read(self.stack / "procs_state.json") or {}
        return s.get("procs", {})
    def row(self, n):
        return self.rows().get(n)
    def ctl(self, doc):
        write(self.stack / "procs_ctl.json", doc)
    def shutdown(self):
        subprocess.run(["aos-daemon-ctl", "-d", str(self.stack), "shutdown", "--timeout-s", "30"], timeout=40)
        if self.p: self.p.wait(timeout=30)
    def kill9(self):
        assert os.readlink(f"/proc/{self.p.pid}/cwd") == str(self.root)
        os.kill(self.p.pid, signal.SIGKILL); self.p.wait()
def kill_mine(pid, root):
    cwd = os.readlink(f"/proc/{pid}/cwd")
    assert cwd.startswith(str(root)), cwd
    os.kill(pid, signal.SIGKILL)
