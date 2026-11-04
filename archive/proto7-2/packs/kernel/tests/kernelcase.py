"""kernel 包測試共用：一個 node `a`（keep 任務 `brain`＝sleep），kernel 由測試手動起（不經核心，才帶得到
AOS7_TEST_CRASH），它的槽是 `a/kslot/`，tock.json 由測試寫。目標的 ctl.json 由真的核心 tick／tock 處理。

    self.cfg(rules=[...])        寫 a/kernel/kernel.json
    self.tock_kernel(n, crash=)  寫 kslot/tock.json 第 n 回合，跑 kernel `run --rounds 1`，回 CompletedProcess
    self.core_round()            a 跑一次 tick＋tock（處理 ctl.json、keep 重起）
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
TOP = os.path.dirname(os.path.dirname(PACK))
sys.path.insert(0, os.path.join(TOP, "tests"))
sys.path.insert(0, PACK)

from base import CoreCase  # noqa: E402,F401
from aos7_fs import read_json, write_json  # noqa: E402

FAKE = os.path.join(HERE, "kernel_fake.py")
KERNEL = os.path.join(PACK, "bin", "aos7-kernel")
PY = sys.executable
RUN = 1
BRAIN = {"node": "a", "slot": "brain"}


class KernelMixin:
    """要 CoreCase。setUp 時呼叫 self.setup_kernel()。"""

    def setup_kernel(self, start_brain=True):
        self.node = self.mknode("a", [{"name": "brain", "mode": "keep", "argv": ["sleep", "1000"]}], interval_ms=0)
        self.kslot = os.path.join(self.node, "kslot")
        os.makedirs(self.kslot, exist_ok=True)
        if start_brain:
            self.core_round()

    def cfg(self, rules, sources=None, targets=None, **extra):
        c = {"v": 1, "sources": sources or [dict(BRAIN, kind="brain")], "targets": targets or [dict(BRAIN)],
             "rules": rules, "events": False}
        c.update(extra)
        write_json(os.path.join(self.node, "kernel", "kernel.json"), c)
        return c

    def kenv(self, crash=None, extra=None):
        e = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=self.node, AOS7_NODE_ID="a", AOS7_TASK=self.kslot,
                 AOS7_TID="kernel", AOS7_RUN=str(RUN))
        if crash:
            e["AOS7_TEST_CRASH"] = crash
        e.update(extra or {})
        return e

    def kernel(self, *args, crash=None, extra=None, entry=FAKE, timeout=30):
        return subprocess.run([PY, "-B", entry, *args], capture_output=True, text=True, timeout=timeout,
                              cwd=self.node, env=self.kenv(crash, extra), start_new_session=True)

    def tock_kernel(self, n, crash=None, extra=None):
        write_json(os.path.join(self.kslot, "tock.json"), {"run": RUN, "round": n, "at": "t"})
        return self.kernel("run", "--rounds", "1", crash=crash, extra=extra)

    def core_round(self):
        self.tick("a")
        return self.tock("a")

    def state(self):
        return read_json(os.path.join(self.kslot, "state.json"))

    def decisions(self):
        return read_json(os.path.join(self.kslot, "decisions.json"))

    def brain_slot(self):
        return self.slot(self.node, "brain")

    def brain_run(self):
        return self.birth(self.node, "brain").get("run")

    def ctl(self):
        return read_json(os.path.join(self.brain_slot(), "ctl.json"))

    def receipt(self):
        return read_json(os.path.join(self.brain_slot(), "ctl-done.json"))

    def kill_rule(self, frm=1, why="測試", until=10 ** 9):
        return {"name": "echo", "from": frm, "until": until, "emit": [{"op": "kill", "target": dict(BRAIN), "run": "$run", "why": why,
                                                       "basis": {"t": "test"}}]}

    def show(self, p):
        return "rc=%s\nout=%s\nerr=%s\nstate=%s" % (p.returncode, p.stdout, p.stderr,
                                                    json.dumps(self.state(), ensure_ascii=False)[:1500])
