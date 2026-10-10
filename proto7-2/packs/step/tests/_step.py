"""〔step〕step 任務包：步驟表直譯器、子工作包裝程式、結果檔、檢查器（packs/step/spec.md）。

兩種跑法都是真的回合、離線、不打 LLM：
- **daemon**（DaemonCase）：正常走通、pause 時耐性不走、多回合檔案數不長、wake。
- **手動 tick／tock**（子程序 bin/aos7-tick、aos7-tock）：中斷探針要卡在確定的點，手動推回合才不會有時序賭運氣。
  直譯器本身仍是 tick 起的 keep 任務；每次 tock 後等它把這個 tock 處理完（frame.json 的 `tock`）再往下。

直譯器的 SIGKILL 點用包自己的鉤子：工作資料夾放 `.step-crash` 寫點名（after-intent／after-add／before-accept），
直譯器到那點就刪檔、殺自己（不碰核心的 AOS7_TEST_*）。
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
TOP = os.path.dirname(os.path.dirname(PACK))
sys.path.insert(0, os.path.join(TOP, "tests"))
sys.path.insert(0, PACK)

from base import DaemonCase  # noqa: E402
from _matrix import MatrixCase, alive, dead_pid  # noqa: E402
from aos7_fs import edit_json, read_json, write_json  # noqa: E402
import aos7_ctl  # noqa: E402
import aos7_step  # noqa: E402

STEP = os.path.join(PACK, "bin", "aos7-step")
CHILD = os.path.join(HERE, "child.py")
EXAMPLES = os.path.join(PACK, "examples")
PY = sys.executable


def child(name, art="-", gate="-", code=0):
    return [PY, CHILD, name, art, gate, str(code)]


def probe_table(job, a=None, b=None, gate=False):
    """兩步探針表：a（寫產物 out/a.txt，可帶閘門）→ b → done。a、b 可覆蓋欄位。"""
    return {"job": job, "start": "a", "steps": {
        "a": dict({"run": child(job + "-a", "${out}/a.txt", "${job}/gate-a" if gate else "-"), "finite": True,
                   "idempotent": True, "expect": ["${out}/a.txt"], "ok": "b"}, **(a or {})),
        "b": dict({"run": child(job + "-b", "${out}/b.txt"), "finite": True, "idempotent": True, "ok": "done"},
                  **(b or {})),
        "done": {"end": "ok"}}}


class StepCase(MatrixCase, DaemonCase):
    """共用：裝工作、讀框架、手動推回合、收直譯器。"""

    def install(self, node, job, table=None, example=None, **opts):
        """把範例（或給的表）放到 <node>/jobs/<job>/；回直譯器的 tasks.json 項。"""
        jd = os.path.join(node, "jobs", job)
        if example:
            shutil.copytree(os.path.join(EXAMPLES, example), jd)
            table = table or read_json(os.path.join(jd, "steps.json"))
        os.makedirs(jd, exist_ok=True)
        if opts:
            table = dict(table, options=dict(table.get("options", {}), **opts))
        write_json(os.path.join(jd, "steps.json"), table)
        return {"name": "step-" + job, "mode": "keep", "argv": [PY, STEP, "run", "jobs/" + job]}

    def jd(self, node, job, *a):
        return os.path.join(node, "jobs", job, *a)

    def frame(self, node, job):
        return read_json(self.jd(node, job, "frame.json")) or {}

    def err(self, node, job):
        return read_json(self.jd(node, job, "error.json")) or {}

    def results(self, node, job, step):
        d = self.jd(node, job, "results", step)
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def step_items(self, node, step=None):
        return [i for i in self.tasks(node) or [] if (i.get("x") or {}).get("step")
                and (step is None or i["x"]["step"]["step"] == step)]

    def wait_pass(self, node, job, rnd, timeout=10):
        """等直譯器處理完第 rnd 回合的 tock（框架或 error.json 的 tock ≥ rnd、工作已結束，或直譯器這個 run 已經死了）。"""
        def done():
            b, ex = self.birth(node, "step-" + job), self.exit_of(node, "step-" + job)
            if not b or (isinstance(ex, dict) and ex.get("run") == b.get("run")):
                return True
            fr = self.frame(node, job)
            if fr.get("phase") == "ended" or (isinstance(fr.get("tock"), int) and fr["tock"] >= rnd):
                return True
            e = self.err(node, job)
            return isinstance(e.get("tock"), int) and e["tock"] >= rnd
        self.wait_for(done, timeout, "直譯器沒處理第 %d 回合的 tock：frame=%r err=%r"
                      % (rnd, self.frame(node, job), self.err(node, job)))

    def cycle(self, node, job, wait=True):
        """一個回合：tick、等這回合起的子工作與直譯器的啟動圈、tock、等直譯器處理完。回回合號。"""
        out = self.tick()
        rnd = out["round"]
        if wait:
            # 剛被 tick 起來的直譯器先跑啟動圈；等它把框架寫到這回合（或出錯）才 tock，免得跟 tock 搶
            if any(r.startswith("step-%s#" % job) for r in out["started"]):
                self.wait_for(lambda: (self.frame(node, job).get("seen") or 0) >= rnd
                              or (self.err(node, job).get("round") or 0) >= rnd
                              or self.frame(node, job).get("phase") == "ended"
                              or self.exit_of(node, "step-" + job), 10, "直譯器啟動圈沒跑完")
        self.tock()
        if wait:
            self.wait_pass(node, job, rnd)
        return rnd

    def run_until(self, node, job, pred, limit=12, msg="沒走到"):
        for _ in range(limit):
            if pred():
                return
            self.cycle(node, job)
        self.assertTrue(pred(), "%s：frame=%r err=%r" % (msg, self.frame(node, job), self.err(node, job)))

    def kill_interp(self, node, job):
        """SIGKILL 直譯器的程序群組，等 runner 寫好 exit.json。"""
        pj = self.wait_pid(node, "step-" + job)
        os.killpg(pj["pgid"], signal.SIGKILL)
        self.wait_for(lambda: not alive(pj["pid"]), 5, "直譯器收不掉")
        self.wait_ended(node, "step-" + job, pj["run"])

    def crash_at(self, node, job, point):
        with open(self.jd(node, job, ".step-crash"), "w") as f:
            f.write(point)

    def set_enabled(self, node, name, on):
        def fn(t):
            for i in t["tasks"]:
                if i.get("name") == name:
                    i["enabled"] = on
            return t
        edit_json(os.path.join(node, ".aos", "tasks.json"), fn)

    def reap_space(self):
        """收掉這個空間裡的程序、刪掉 node（同一個測試裡換下一個情境用）。"""
        from base import kill_space_procs
        for _ in range(3):
            if not kill_space_procs(self.root):
                break
            time.sleep(0.05)
        shutil.rmtree(os.path.join(self.root, "a"), ignore_errors=True)

    def step_cli(self, node, *args):
        return subprocess.run([PY, STEP, *args], cwd=node, capture_output=True, text=True, timeout=30)


