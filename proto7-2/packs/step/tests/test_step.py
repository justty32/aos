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


# ---------------------------------------------------------------- 檢查器

class TestCheck(unittest.TestCase):
    """〔step〕檢查器：結構＋R1／R2／R3；兩個範例都過。"""

    def rules(self, t):
        return sorted({(i["rule"], i["step"]) for i in aos7_step.check(t) if i["level"] == "error"})

    def test_examples_pass(self):
        for ex in ("csv", "backup"):
            r = subprocess.run([PY, STEP, "check", os.path.join(EXAMPLES, ex, "steps.json")], capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(json.loads(r.stdout), [])

    def test_r2_non_idempotent_in_retry_loop(self):
        """rotate（不冪等）放進重試圈 → R2；改成先查回條（receipt）就過；on_unknown: resend 不冪等 → R2。"""
        t = read_json(os.path.join(EXAMPLES, "backup", "steps.json"))
        t["steps"]["rotate"]["fail"] = "retry_rotate"
        t["steps"]["retry_rotate"] = {"count": 2, "then": "rotate", "exhausted": "failed"}
        self.assertIn(("R2", "rotate"), self.rules(t))
        t["steps"]["rotate"]["receipt"] = {"exists": "${job}/archive/rotated-${step}"}
        self.assertNotIn(("R2", "rotate"), self.rules(t))
        t = read_json(os.path.join(EXAMPLES, "backup", "steps.json"))
        t["steps"]["rotate"]["on_unknown"] = "resend"
        self.assertEqual(self.rules(t), [("R2", "rotate")])
        r = subprocess.run([PY, STEP, "check", "/dev/stdin"], input=json.dumps(t), capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_r1_finite_or_patience(self):
        t = probe_table("j")
        del t["steps"]["a"]["finite"]
        self.assertEqual(self.rules(t), [("R1", "a")])
        t["steps"]["a"]["patience"] = 5
        self.assertEqual(self.rules(t), [])

    def test_r3_only_local_rounds(self):
        for bad in ({"patience_s": 5}, {"patience": "5s"}, {"patience": {"rounds": 5, "clock": "wall"}},
                    {"deadline": "2026-10-05"}, {"patience": 1.5}):
            t = probe_table("j", a=bad)
            self.assertIn(("R3", "a"), self.rules(t), bad)

    def test_structure(self):
        t = probe_table("j", a={"ok": "nowhere"})
        self.assertIn(("struct", "a"), self.rules(t))
        t = probe_table("j", b={"run": ["echo", "${nope}"]})
        self.assertIn(("struct", "b"), self.rules(t))
        t = probe_table("j")
        t["steps"]["w"] = {"wait": {"exists": "x", "glob": "y"}, "then": "done"}      # 條件只能一種
        t["steps"]["v"] = {"wait": {"expr": "a and b"}, "then": "done"}              # 不開運算式
        t["steps"]["k"] = {"wait": {"exists": "x"}, "then": "done", "patience": 2, "on_timeout": "kill"}
        t["steps"]["two"] = {"run": ["true"], "end": "x", "ok": "done"}
        got = self.rules(t)
        for s in ("w", "v", "k", "two"):
            self.assertIn(("struct", s), got)
        self.assertEqual(self.rules({"steps": {}}), [("struct", None)])

    def test_bad_types_json_diagnostics(self):
        """start=[]、ok=[]、result.ok=[]：CLI 回 JSON 診斷陣列（error）、rc 1、stderr 沒有 traceback（A4-04）。"""
        t1 = probe_table("j")
        t1["start"] = []
        t2 = probe_table("j", a={"ok": []})
        t3 = probe_table("j")
        t3["steps"]["w"] = {"wait": {"result.ok": []}, "then": "done"}
        for case, t in (("start", t1), ("ok", t2), ("result.ok", t3)):
            with self.subTest(case=case):
                r = subprocess.run([PY, STEP, "check", "/dev/stdin"], input=json.dumps(t), capture_output=True,
                                   text=True)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertNotIn("Traceback", r.stderr)
                got = json.loads(r.stdout)
                self.assertTrue(any(i["level"] == "error" for i in got), got)

    def test_global_kill_on_wait(self):
        """全域 on_timeout: kill＋wait 步 → error（查套預設後的有效值）；步內改回 unknown 就過（A4-04）。"""
        t = probe_table("j", b={"ok": "w"})
        t["options"] = {"on_timeout": "kill"}
        t["steps"]["w"] = {"wait": {"exists": "x"}, "patience": 2, "then": "done"}
        self.assertEqual(self.rules(t), [("struct", "w")])
        t["steps"]["w"]["on_timeout"] = "unknown"
        self.assertEqual(self.rules(t), [])

    def test_run_step_wake(self):
        """run 步可逐步覆蓋 wake（A4-07）；型別要是 true／false；restart_on_end 不能寫在步內。"""
        self.assertEqual(self.rules(probe_table("j", a={"wake": True})), [])
        self.assertEqual(self.rules(probe_table("j", a={"wake": "yes"})), [("struct", "a")])
        self.assertEqual(self.rules(probe_table("j", a={"restart_on_end": True})), [("struct", "a")])

    def test_unknown_codes_type(self):
        """unknown_codes（run 步，A8-10）：非空、互異、1～255 的真整數陣列才過。"""
        for codes in ([3], [3, 75], [], [0], ["3"], [True], 3, [256], [3, 3]):
            with self.subTest(codes=codes):
                self.assertEqual(self.rules(probe_table("j", a={"unknown_codes": codes})),
                                 [] if codes in ([3], [3, 75]) else [("struct", "a")])

    def test_max_resends_type(self):
        """max_resends（run 步）：非負整數才過；0 也合法（＝不自動重送）。"""
        for v in (0, 1, 3):
            self.assertEqual(self.rules(probe_table("j", a={"on_unknown": "resend", "max_resends": v})), [], v)
        for v in (-1, True, "2", 1.5, None):
            self.assertEqual(self.rules(probe_table("j", a={"on_unknown": "resend", "max_resends": v})),
                             [("struct", "a")], v)


# ---------------------------------------------------------------- daemon：正常走通、pause、檔案數、wake

class TestStepDaemon(StepCase):
    """〔step〕真的 daemon：兩個範例走通、pause 時耐性不走、重複跑檔案數不長、wake 選項。"""

    def test_csv_end_to_end(self):
        """CSV→JSON→報表：兩步各一個核心 run（不同槽），第二步只讀第一步已採用的 request，結果檔各一份。"""
        node = self.mknode("a", interval_ms=50)
        self.set_tasks(node, [self.install(node, "csv", example="csv")])
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.frame(node, "csv").get("phase") == "ended", 20, "csv 沒跑完")
        fr = self.frame(node, "csv")
        self.assertEqual(fr["end"], "ok", fr)
        acc = fr["accepted"]
        self.assertTrue(acc["convert"]["run"].startswith("step-csv-convert#"), acc)
        self.assertTrue(acc["stats"]["run"].startswith("step-csv-stats#"), acc)
        rep = read_json(self.jd(node, "csv", "out", "report.json"))
        self.assertEqual(rep["from"], acc["convert"]["request"])
        self.assertEqual(rep["rows"], 5)
        self.assertEqual(rep["by_dept"]["eng"], {"n": 2, "sum": 200.0, "avg": 100.0})
        self.assertEqual(len(self.results(node, "csv", "convert")), 1)
        self.assertEqual(len(self.results(node, "csv", "stats")), 1)
        res = read_json(self.jd(node, "csv", "results", "convert", self.results(node, "csv", "convert")[0]))
        self.assertEqual(res["run"], acc["convert"]["run"])
        self.assertIn("jobs/csv/out/data.json", res["artifacts"])
        self.assertEqual(self.step_items(node), [])
        done = os.path.join(self.root, ".aosd", "ctl-done")
        self.assertEqual([n for n in os.listdir(done) if ".wake." in n], [])     # wake 預設 false
        st = self.step_cli(node, "status", "jobs/csv")
        self.assertEqual(json.loads(st.stdout)["end"], "ok", st.stderr)

    def test_backup_end_to_end(self):
        """備份四步走通：rotate 一次、通知帶 request；dump 失敗兩次後成功（count 計數 2）。"""
        node = self.mknode("a", interval_ms=50)
        item = self.install(node, "backup", example="backup")
        jd = self.jd(node, "backup")
        with open(os.path.join(jd, "dump.sh")) as f:
            body = f.read()
        with open(os.path.join(jd, "dump.sh"), "w") as f:     # 前兩次故意失敗
            f.write('n=$(cat "$1/../tries" 2>/dev/null || echo 0); echo $((n+1)) > "$1/../tries"\n'
                    '[ "$n" -ge 2 ] || exit 1\n' + body)
        self.set_tasks(node, [item])
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.frame(node, "backup").get("phase") == "ended", 30, "backup 沒跑完")
        fr = self.frame(node, "backup")
        self.assertEqual(fr["end"], "ok", fr)
        self.assertEqual(fr["counts"], {"retry_dump": 2})
        self.assertEqual(len(self.results(node, "backup", "dump")), 3)
        with open(os.path.join(jd, "archive", "rotations.log")) as f:
            self.assertEqual(f.read().split(), ["rotated"])
        with open(os.path.join(jd, "out", "notify.txt")) as f:
            self.assertIn(fr["accepted"]["notify"]["request"], f.read())

    def test_pause_freezes_patience(self):
        """wait 步耐性 10 回合；pause node 1.5 秒（≈15 個 interval）：框架不動、不逾時；resume 後條件成立照常結束。"""
        node = self.mknode("a", interval_ms=100)
        t = {"job": "pz", "start": "a", "steps": {
            "a": {"run": child("pz-a"), "finite": True, "ok": "w"},
            "w": {"wait": {"exists": "${job}/ack"}, "patience": 10, "then": "done"},
            "done": {"end": "ok"}}}
        self.set_tasks(node, [self.install(node, "pz", t)])
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.frame(node, "pz").get("pc") == "w"
                      and self.frame(node, "pz")["seen"] > self.frame(node, "pz")["since"], 15, "沒走到 w")
        self.prog("aos7-ctl", "daemon", self.root, "pause", "a", "--owner", "t")
        self.wait_for(lambda: self.nstat().get("phase") == "paused", 10, "沒 pause")
        time.sleep(0.3)                                          # 最後一個 tock 的那一圈寫完
        before, rnd = self.frame(node, "pz"), self.node_round()
        time.sleep(1.5)
        after = self.frame(node, "pz")
        self.assertEqual((after["rev"], after["seen"], after["phase"], after["halt"]),
                         (before["rev"], before["seen"], "running", None))
        self.assertEqual(self.node_round(), rnd)
        self.prog("aos7-ctl", "daemon", self.root, "resume", "a", "--owner", "t")
        open(self.jd(node, "pz", "ack"), "w").close()
        self.wait_for(lambda: self.frame(node, "pz").get("phase") == "ended", 10, "resume 後沒結束")
        self.assertEqual(self.frame(node, "pz")["end"], "ok")

    def test_file_count_bounded(self):
        """restart_on_end：同一個工作跑 6 次，結案時清結果，工作資料夾檔數與槽數不隨次數長。"""
        node = self.mknode("a", interval_ms=20)
        self.set_tasks(node, [self.install(node, "csv", example="csv", restart_on_end=True)])
        self.start_daemon(register=["a"])
        seen = {}

        def files():
            return sum(len(fs) for _, _, fs in os.walk(self.jd(node, "csv")))

        def sample():
            fr = self.frame(node, "csv")
            if fr.get("phase") == "ended" and fr["inst"] not in seen:
                n, slots = files(), os.listdir(os.path.join(node, ".aos", "tasks"))
                if self.frame(node, "csv").get("rev") == fr["rev"]:     # 數的時候沒換人
                    seen[fr["inst"]] = (n, len(slots))
            return len(seen) >= 6
        self.wait_for(sample, 60, "沒跑滿 6 次")
        counts = [v[0] for v in seen.values()]
        self.assertEqual(len(set(counts[1:])), 1, seen)
        self.assertTrue(all(v[1] <= 3 for v in seen.values()), seen)   # 直譯器＋兩個 once 槽

    def test_wake_option(self):
        """wake: true：登記完 once 就寫 daemon 的 wake（回條 ok）；預設不寫。"""
        node = self.mknode("a", interval_ms=300)
        self.set_tasks(node, [self.install(node, "wk", probe_table("wk"), wake=True)])
        self.start_daemon(register=["a"])
        self.wait_for(lambda: self.frame(node, "wk").get("phase") == "ended", 20, "沒跑完")
        done = os.path.join(self.root, ".aosd", "ctl-done")
        rs = [read_json(os.path.join(done, n)) for n in os.listdir(done) if ".wake." in n]
        self.assertTrue(rs and all(r["result"]["ok"] for r in rs), rs)
        self.assertTrue(any(r["by"] == "a:step-wk" for r in rs), rs)


# ---------------------------------------------------------------- 手動回合：中斷探針

class TestStepProbes(StepCase):
    """〔step〕中斷探針（astra 探針表、綜合 §1 第 6 點）：手動 tick／tock，直譯器是真的 keep 任務。"""

    def setup_job(self, job, table):
        node = self.mknode("a")
        self.set_tasks(node, [self.install(node, job, table)])
        return node

    def test_expired_intent_unknown(self):
        """過期 intent（R8-13）：不再直接停，走 on_unknown——stop 停 unknown、receipt 當 ok、resend 同 request 派 a2。"""
        for mode in ("stop", "receipt", "resend"):
            with self.subTest(mode=mode):
                a = {"receipt": {"exists": "${job}/rcpt"}} if mode == "receipt" else {"on_unknown": mode}
                node = self.setup_job("ei", probe_table("ei", a=a))
                self.crash_at(node, "ei", "after-intent")
                self.cycle(node, "ei")
                self.wait_ended(node, "step-ei")
                req = self.frame(node, "ei")["pending"]["request"]
                self.set_enabled(node, "step-ei", False)
                if mode == "receipt":
                    open(self.jd(node, "ei", "rcpt"), "w").close()
                for _ in range(4):
                    self.cycle(node, "ei", wait=False)
                self.set_enabled(node, "step-ei", True)
                self.run_until(node, "ei", lambda: self.frame(node, "ei").get("phase") in ("halted", "ended"))
                fr = self.frame(node, "ei")
                if mode == "stop":
                    self.assertEqual((fr["halt"]["kind"], fr["pending"]["state"]), ("unknown", "intent"))
                elif mode == "receipt":
                    self.assertTrue(fr["accepted"]["a"]["receipt"])
                else:
                    self.assertEqual(fr["end"], "ok")
                    self.assertEqual(fr["accepted"]["a"]["request"], req)
                    self.assertTrue(fr["accepted"]["a"]["attempt"].endswith("-a2"))
                self.assertEqual(len(self.ran(node, "ei-a")), int(mode == "resend"))
                self.reap_space()

    def test_intent_round_tick_overlap(self):
        """R8-22 時序驗證：直譯器讀到回合 r（tick r 已開、還沒讀表）就加項，once 在 r 起、沒結果就死、tock r+1 刪槽；
        r+1 時不准補加同一 attempt（D5 縮窗：補加只准同回合）→ halt unknown、只跑一次。舊窗口（≤ intent_round+1）會跑兩次。"""
        node = self.mknode("a")
        self.install(node, "ov", probe_table("ov", gate=True))
        self.set_tasks(node, [])
        open(self.jd(node, "ov", "gate-a"), "w").close()
        r = self.tick()["round"] + 1
        self.tock()
        def one(override=False):
            code = "import sys; sys.path.insert(0, %r); import aos7_step as s; " % PACK
            if override:
                code += "orig=s.node_round; calls=iter([%d]); s.node_round=lambda *a: next(calls, None) or orig(*a); " % r
            return subprocess.run([PY, "-c", code + "s.run_pass(sys.argv[1], int(sys.argv[2]))",
                                   "jobs/ov", str(r if override else r + 1)], cwd=node,
                                  env=dict(os.environ), timeout=30).returncode
        self.crash_at(node, "ov", "after-add")
        self.assertEqual(one(True), -9)
        p = self.frame(node, "ov")["pending"]
        self.assertEqual((p["state"], p["intent_round"]), ("intent", r))
        self.assertEqual(self.step_items(node)[0]["x"]["step"]["attempt"], p["attempt"])
        self.assertEqual(self.tick()["round"], r)
        self.wait_for(lambda: os.path.exists(self.jd(node, "ov", "gate-a.entered")))
        os.killpg(self.wait_pid(node, "step-ov-a")["pgid"], signal.SIGKILL)
        self.wait_ended(node, "step-ov-a")
        self.assertEqual(self.results(node, "ov", "a"), [])
        self.tock()
        self.tick()
        self.tock()
        self.assertFalse(os.path.exists(self.slot(node, "step-ov-a")))
        self.assertEqual(one(), 0)
        for _ in range(2):
            self.tick()
            self.tock()
        self.wait_for(lambda: len(self.ran(node, "ov-a")) >= 1)
        self.assertEqual(len(self.ran(node, "ov-a")), 1)
        self.assertEqual(self.frame(node, "ov")["halt"]["kind"], "unknown")

    def test_sweep_dead_tmp(self):
        """C8-03 step 份：直譯器啟動時清工作資料夾與 results/<步>/ 裡寫者已死的暫存檔，活寫者的不碰。"""
        node = self.setup_job("tmp", probe_table("tmp"))
        os.makedirs(self.jd(node, "tmp", "results", "a"))
        paths = [self.jd(node, "tmp", ".frame.json.tmp.%d" % dead_pid()),
                 self.jd(node, "tmp", "results", "a", ".x.json.tmp.%d" % dead_pid()),
                 self.jd(node, "tmp", ".keep.json.tmp.%d" % os.getpid())]
        for path in paths:
            open(path, "w").close()
        self.run_until(node, "tmp", lambda: self.frame(node, "tmp").get("phase") == "ended")
        self.assertEqual([os.path.exists(path) for path in paths], [False, False, True])

    def test_interp_killed_reattaches_same_attempt(self):
        """子工作還在跑時 SIGKILL 直譯器：keep 重開接回同一個 attempt，不多派；放閘門後照常走完。"""
        node = self.setup_job("k", probe_table("k", gate=True))
        open(self.jd(node, "k", "gate-a"), "w").close()
        self.run_until(node, "k", lambda: os.path.exists(self.jd(node, "k", "gate-a.entered")), msg="a 沒起")
        att = self.frame(node, "k")["pending"]["attempt"]
        self.kill_interp(node, "k")
        for _ in range(3):
            self.cycle(node, "k")
            self.assertEqual(self.step_items(node, "a"), [])
        self.assertEqual(self.frame(node, "k")["pending"]["attempt"], att)
        os.unlink(self.jd(node, "k", "gate-a"))
        self.run_until(node, "k", lambda: self.frame(node, "k").get("phase") == "ended", msg="沒走完")
        fr = self.frame(node, "k")
        self.assertEqual((fr["end"], fr["accepted"]["a"]["attempt"]), ("ok", att))
        self.assertEqual((len(self.ran(node, "k-a")), len(self.ran(node, "k-b"))), (1, 1))

    def test_crash_points_advance_once(self):
        """先驗 SIGKILL 與死亡快照，再恢復；過期 intent 要人手重送。"""
        for point in ("after-intent", "after-add", "before-accept"):
            with self.subTest(point=point):
                job = point.replace("-", "")
                node = self.setup_job(job, probe_table(job))
                self.crash_at(node, job, point)
                for _ in range(12):
                    self.cycle(node, job)
                    b, ex = self.birth(node, "step-" + job), self.exit_raw(node, "step-" + job)
                    if not os.path.exists(self.jd(node, job, ".step-crash")):
                        self.wait_ended(node, "step-" + job, b["run"])
                        ex = self.exit_raw(node, "step-" + job)
                        self.assertEqual((ex["run"], ex["code"]), (b["run"], -9))
                        break
                else:
                    self.fail("%s 沒打中" % point)
                # 全是手動回合，下一次 tick 前 keep 不會重開。
                fr = self.frame(node, job)
                p = fr["pending"]
                if point == "before-accept":
                    self.assertTrue(self.results(node, job, "a"))
                    self.assertNotIn("a", fr["accepted"])
                    self.assertEqual(fr["pc"], "a")
                else:
                    self.assertEqual(p["state"], "intent")
                    if point == "after-intent":
                        self.assertEqual(self.step_items(node), [])
                    else:
                        self.assertTrue(any(i["x"]["step"]["attempt"] == p["attempt"]
                                            for i in self.step_items(node))
                                        or aos7_step.attempt_of(self.birth(node, p["task"])) == p["attempt"])
                if point == "after-intent":
                    self.run_until(node, job, lambda: self.frame(node, job).get("phase") == "halted")
                    self.assertEqual(self.frame(node, job)["halt"]["kind"], "unknown")
                    self.assertEqual(self.ran(node, job + "-a"), [])
                    self.assertEqual(self.step_cli(node, "resume", "jobs/" + job, "--resend").returncode, 0)
                self.run_until(node, job, lambda: self.frame(node, job).get("phase") == "ended", msg=point)
                fr = self.frame(node, job)
                self.assertEqual(fr["end"], "ok", fr)
                self.assertEqual((len(self.ran(node, job + "-a")), len(self.ran(node, job + "-b"))), (1, 1), point)
                self.assertEqual(fr["visits"], {"a": 1, "b": 1, "done": 1})
                self.assertEqual(sorted(fr["tries"].values()), [1, 2] if point == "after-intent" else [1, 1])
                if point == "after-intent":
                    self.assertTrue(fr["accepted"]["a"]["attempt"].endswith("-a2"))
                self.assertFalse(os.path.exists(self.jd(node, job, ".step-crash")), "%s 沒打中" % point)
                self.reap_space()

    def test_once_slot_gone_result_carries_on(self):
        """直譯器停了好幾回合、子工作的 once 槽已被刪：重開後靠槽外結果繼續，不重派。"""
        node = self.setup_job("g", probe_table("g"))
        self.cycle(node, "g")                                    # 第 1 回合：直譯器派 a
        self.kill_interp(node, "g")
        self.set_enabled(node, "step-g", False)
        self.cycle(node, "g", wait=False)                        # 第 2 回合：tick 起 a
        self.wait_for(lambda: self.results(node, "g", "a"), 10, "a 沒結果")
        for _ in range(3):                                       # 報完再一回合，槽被刪
            self.cycle(node, "g", wait=False)
        self.assertFalse(os.path.exists(self.slot(node, "step-g-a")), "a 的槽還在，測不到")
        self.assertEqual(len(self.results(node, "g", "a")), 1)
        self.set_enabled(node, "step-g", True)
        self.run_until(node, "g", lambda: self.frame(node, "g").get("phase") == "ended")
        self.assertEqual((len(self.ran(node, "g-a")), len(self.ran(node, "g-b"))), (1, 1))

    def test_killed_after_artifact_before_result(self):
        """產物寫了、結果沒寫時 kill 子工作：停在 unknown（不誤報成功、不當沒做、不自動重送）。"""
        node = self.setup_job("u", probe_table("u", gate=True))
        open(self.jd(node, "u", "gate-a"), "w").close()
        self.run_until(node, "u", lambda: os.path.exists(self.jd(node, "u", "gate-a.entered")), msg="a 沒起")
        self.assertTrue(os.path.exists(self.jd(node, "u", "out", "a.txt")))
        aos7_ctl.task_ctl(self.slot(node, "step-u-a"), why="probe", run=self.birth(node, "step-u-a")["run"])
        self.run_until(node, "u", lambda: self.frame(node, "u").get("phase") == "halted", msg="沒停住")
        for _ in range(3):
            self.cycle(node, "u")
        fr = self.frame(node, "u")
        self.assertEqual(fr["halt"]["kind"], "unknown", fr)
        self.assertIn("沒有結果檔", fr["halt"]["why"])
        self.assertNotIn("a", fr["accepted"])
        self.assertEqual(self.results(node, "u", "a"), [])
        self.assertEqual(self.step_items(node), [])
        self.assertEqual(len(self.ran(node, "u-a")), 1)
        self.assertEqual(self.ran(node, "u-b"), [])
        # 人看過之後 resume --resend：同一個 request、新 attempt
        os.unlink(self.jd(node, "u", "gate-a"))
        r = self.step_cli(node, "resume", "jobs/u", "--resend")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.run_until(node, "u", lambda: self.frame(node, "u").get("phase") == "ended")
        acc = self.frame(node, "u")["accepted"]["a"]
        self.assertEqual((acc["request"].endswith("-a-1"), acc["attempt"].endswith("-a2")), (True, True), acc)

    def test_backup_rotate_unknown_not_retried(self):
        """備份：rotate（不冪等）轉完、結果寫出前被殺 → unknown 停住，不重送（只轉過一次）。"""
        node = self.mknode("a")
        item = self.install(node, "bk", example="backup")
        jd = self.jd(node, "bk")
        with open(os.path.join(jd, "rotate.sh"), "a") as f:
            f.write('touch "$2/../gate.entered"; while [ -e "$2/../gate" ]; do sleep 0.03; done\n')
        open(os.path.join(jd, "gate"), "w").close()
        self.set_tasks(node, [item])
        self.run_until(node, "bk", lambda: os.path.exists(os.path.join(jd, "gate.entered")), limit=15,
                       msg="rotate 沒起")
        slot = "step-backup-rotate"          # 槽名取表上的 job（backup），不是資料夾名
        aos7_ctl.task_ctl(self.slot(node, slot), why="probe", run=self.birth(node, slot)["run"])
        self.run_until(node, "bk", lambda: self.frame(node, "bk").get("phase") == "halted", msg="沒停住")
        for _ in range(3):
            self.cycle(node, "bk")
        fr = self.frame(node, "bk")
        self.assertEqual((fr["halt"]["kind"], fr["pc"]), ("unknown", "rotate"), fr)
        self.assertEqual(self.step_items(node), [])
        with open(os.path.join(jd, "archive", "rotations.log")) as f:
            self.assertEqual(f.read().split(), ["rotated"])        # 只轉過一次

    def test_backup_rotate_fail_not_retried(self):
        """備份：rotate 直接失敗 → 走 fail（結束 failed），不重試。"""
        node = self.mknode("a")
        item = self.install(node, "bf", example="backup")
        with open(self.jd(node, "bf", "rotate.sh"), "w") as f:
            f.write("exit 1\n")
        self.set_tasks(node, [item])
        self.run_until(node, "bf", lambda: self.frame(node, "bf").get("phase") == "ended", limit=15)
        fr = self.frame(node, "bf")
        self.assertEqual(fr["end"], "failed", fr)
        self.assertEqual(len(self.results(node, "bf", "rotate")), 1)
        self.assertEqual(fr["tries"][fr["accepted"]["rotate"]["request"]], 1)

    def test_idempotent_resend_keeps_request(self):
        """冪等步＋on_unknown: resend：被殺後自動重派一次，request 不變、attempt +1。"""
        node = self.setup_job("r", probe_table("r", a={"on_unknown": "resend"}, gate=True))
        open(self.jd(node, "r", "gate-a"), "w").close()
        self.run_until(node, "r", lambda: os.path.exists(self.jd(node, "r", "gate-a.entered")), msg="a 沒起")
        first = self.frame(node, "r")["pending"]
        aos7_ctl.task_ctl(self.slot(node, "step-r-a"), why="probe", run=self.birth(node, "step-r-a")["run"])
        self.run_until(node, "r", lambda: (self.frame(node, "r").get("pending") or {}).get("attempt", "").endswith("-a2"),
                       msg="沒重派")
        os.unlink(self.jd(node, "r", "gate-a"))
        self.run_until(node, "r", lambda: self.frame(node, "r").get("phase") == "ended")
        acc = self.frame(node, "r")["accepted"]["a"]
        self.assertEqual(acc["request"], first["request"])
        self.assertEqual(acc["attempt"], first["request"] + "-a2")
        self.assertEqual(len(self.ran(node, "r-a")), 2)

    def test_max_resends_two(self):
        """max_resends: 2：被殺兩次都自動重派（同 request、a2、a3），第三次 unknown 才停；共跑 3 次。"""
        node = self.setup_job("m", probe_table("m", a={"on_unknown": "resend", "max_resends": 2}, gate=True))
        open(self.jd(node, "m", "gate-a"), "w").close()
        req = None
        for k in (1, 2, 3):
            self.run_until(node, "m", lambda: len(self.ran(node, "m-a")) == k
                           and (self.birth(node, "step-m-a") or {}).get("run"), msg="a%d 沒起" % k)
            p = self.frame(node, "m")["pending"]
            req = req or p["request"]
            self.assertEqual((p["request"], p["attempt"]), (req, "%s-a%d" % (req, k)))
            self.wait_for(lambda: os.path.exists(self.jd(node, "m", "gate-a.entered")), 10, "a%d 沒進閘門" % k)
            os.unlink(self.jd(node, "m", "gate-a.entered"))
            aos7_ctl.task_ctl(self.slot(node, "step-m-a"), why="probe", run=self.birth(node, "step-m-a")["run"])
            if k < 3:
                self.run_until(node, "m", lambda: (self.frame(node, "m").get("pending") or {}).get("attempt")
                               == "%s-a%d" % (req, k + 1), msg="沒重派 a%d" % (k + 1))
        self.run_until(node, "m", lambda: self.frame(node, "m").get("phase") == "halted", msg="沒停住")
        fr = self.frame(node, "m")
        self.assertEqual((fr["halt"]["kind"], fr["tries"][req], len(self.ran(node, "m-a"))), ("unknown", 3, 3), fr)

    def test_unknown_codes_results(self):
        """A8-10(b)：退出碼列在 unknown_codes → on_unknown（同 request 新 attempt、受 max_resends 限、超額停 unknown）；
        不開時照舊 halted failed，resume --resend 同 request 派 a2。"""
        for mode in ("once", "always", "default"):
            with self.subTest(mode=mode):
                a = {"run": child("uc-a", "${out}/a.txt", code=3)}
                if mode != "default":
                    a.update(unknown_codes=[3], on_unknown="resend", max_resends=1)
                if mode == "default":
                    a["run"] = ["sh", "${job}/call.sh"]
                node = self.setup_job("uc", probe_table("uc", a=a))
                if mode == "default":
                    with open(self.jd(node, "uc", "call.sh"), "w") as f:
                        f.write("exit 3\n")
                if mode == "once":
                    # 腳本計次；第二次成功，仍用 child 記實際執行。
                    script = 'n=$(cat "$1/n" 2>/dev/null || echo 0); echo $((n+1)) > "$1/n"; c=3; [ "$n" -lt 1 ] || c=0; exec "$2" "$3" uc-a "$1/out/a.txt" - "$c"'
                    t = probe_table("uc", a=dict(a, run=["sh", "-c", script, "sh", "${job}", PY, CHILD]))
                    write_json(self.jd(node, "uc", "steps.json"), t)
                self.run_until(node, "uc", lambda: self.frame(node, "uc").get("phase") in ("halted", "ended"))
                fr = self.frame(node, "uc")
                req = aos7_step.request_of(fr, "a")
                if mode == "default":
                    self.assertEqual(fr["halt"]["kind"], "failed")
                    with open(self.jd(node, "uc", "call.sh"), "w") as f:
                        f.write('mkdir -p jobs/uc/out; touch jobs/uc/out/a.txt; exit 0\n')
                    self.assertEqual(self.step_cli(node, "resume", "jobs/uc", "--resend").returncode, 0)
                    self.run_until(node, "uc", lambda: self.frame(node, "uc").get("phase") == "ended")
                    acc = self.frame(node, "uc")["accepted"]["a"]
                    self.assertEqual((acc["request"], acc["attempt"]), (req, req + "-a2"))
                else:
                    self.assertEqual((fr["tries"][req], fr["resends"][req], len(self.results(node, "uc", "a"))),
                                     (2, 1, 2))
                    self.assertEqual(len(self.ran(node, "uc-a")), 2)
                    if mode == "once":
                        self.assertEqual(fr["end"], "ok")
                        self.assertEqual(fr["accepted"]["a"]["request"], req)
                        self.assertTrue(fr["accepted"]["a"]["attempt"].endswith("-a2"))
                    else:
                        self.assertEqual(fr["halt"]["kind"], "unknown")
                        self.assertNotIn("a", fr["accepted"])
                self.reap_space()

    def test_resend_budget_survives_bad_table(self):
        """R8-14：自動重送額度記在 request 層；重送那次被壞表拒寫後額度不重設，下一次 unknown 就停（共跑 2 次）；
        resume --resend 歸零。"""
        node = self.setup_job("rb", probe_table("rb", a={"on_unknown": "resend", "max_resends": 1}, gate=True))
        open(self.jd(node, "rb", "gate-a"), "w").close()
        self.run_until(node, "rb", lambda: os.path.exists(self.jd(node, "rb", "gate-a.entered")))
        req = self.frame(node, "rb")["pending"]["request"]
        good = self.tasks(node)
        os.killpg(self.wait_pid(node, "step-rb-a")["pgid"], signal.SIGKILL)
        self.wait_ended(node, "step-rb-a")
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write("{bad")
        self.run_until(node, "rb", lambda: self.err(node, "rb").get("kind") == "bad"
                       and self.frame(node, "rb")["pending"] is None)
        self.assertEqual(self.frame(node, "rb")["resends"][req], 1)
        self.set_tasks(node, good)
        os.unlink(self.jd(node, "rb", "gate-a.entered"))
        self.run_until(node, "rb", lambda: os.path.exists(self.jd(node, "rb", "gate-a.entered")))
        self.assertTrue(self.frame(node, "rb")["pending"]["attempt"].endswith("-a3"))
        os.killpg(self.wait_pid(node, "step-rb-a")["pgid"], signal.SIGKILL)
        self.wait_ended(node, "step-rb-a", self.birth(node, "step-rb-a")["run"])
        self.run_until(node, "rb", lambda: self.frame(node, "rb").get("phase") == "halted")
        self.assertEqual((self.frame(node, "rb")["halt"]["kind"], len(self.ran(node, "rb-a"))), ("unknown", 2))
        self.assertEqual(self.step_cli(node, "resume", "jobs/rb", "--resend").returncode, 0)
        self.assertNotIn(req, self.frame(node, "rb")["resends"])

    def test_bad_tasks_json_refused(self):
        """壞 tasks.json：直譯器拒寫（表原封不動）、撤掉意圖、記 error.json；修好後照常派、走完。"""
        node = self.setup_job("t", probe_table("t", gate=True))
        open(self.jd(node, "t", "gate-a"), "w").close()
        self.run_until(node, "t", lambda: os.path.exists(self.jd(node, "t", "gate-a.entered")), msg="a 沒起")
        os.unlink(self.jd(node, "t", "gate-a"))
        self.wait_for(lambda: self.results(node, "t", "a"), 10, "a 沒結果")
        good = self.tasks(node)
        with open(os.path.join(node, ".aos", "tasks.json"), "w") as f:
            f.write("{bad")
        rnd = self.cycle(node, "t")
        with open(os.path.join(node, ".aos", "tasks.json")) as f:
            self.assertEqual(f.read(), "{bad")
        fr, e = self.frame(node, "t"), self.err(node, "t")
        self.assertEqual((fr["pc"], fr["pending"]), ("b", None), fr)
        self.assertEqual((e["kind"], e["tock"]), ("bad", rnd), e)
        write_json(os.path.join(node, ".aos", "tasks.json"), {"tasks": good})
        self.run_until(node, "t", lambda: self.frame(node, "t").get("phase") == "ended")
        fr = self.frame(node, "t")
        self.assertTrue(fr["accepted"]["b"]["attempt"].endswith("-a2"), fr)    # 被拒那次算一個 attempt 號
        self.assertEqual(len(self.ran(node, "t-b")), 1)

    def test_broken_frame_and_changed_table(self):
        """框架壞掉：不前進、記錯、不從結果檔反推；工作進行中改了步驟表：停（version）。"""
        node = self.setup_job("f", probe_table("f"))
        self.cycle(node, "f")                                    # 派了 a
        path = self.jd(node, "f", "frame.json")
        with open(path, "w") as f:
            f.write("{")
        for _ in range(2):
            self.cycle(node, "f")
        self.wait_for(lambda: self.results(node, "f", "a"), 10, "a 沒結果")
        self.cycle(node, "f")
        with open(path) as f:
            self.assertEqual(f.read(), "{")
        self.assertEqual(self.err(node, "f")["kind"], "frame")
        self.assertEqual((self.step_items(node), self.ran(node, "f-b")), ([], []))
        node2 = self.setup_job("v", probe_table("v"))
        self.cycle(node2, "v")
        t = probe_table("v")
        t["note"] = "改過"
        write_json(self.jd(node2, "v", "steps.json"), t)
        self.cycle(node2, "v")
        self.assertEqual(self.frame(node2, "v")["halt"]["kind"], "version")

    def test_wait_timeout_and_receipt(self):
        """wait 耐性 2 回合到期 → 停（timeout，預設 unknown）；條件之後成立、resume 後照走。receipt 成立的 run 步不派。"""
        t = {"job": "w", "start": "a", "steps": {
            "a": {"run": child("w-a", "${out}/a.txt"), "finite": True, "receipt": {"exists": "${out}/a.txt"},
                  "ok": "w"},
            "w": {"wait": {"exists": "${job}/ack"}, "patience": 2, "then": "done"},
            "done": {"end": "ok"}}}
        node = self.setup_job("w", t)
        os.makedirs(self.jd(node, "w", "out"))
        open(self.jd(node, "w", "out", "a.txt"), "w").close()
        self.run_until(node, "w", lambda: self.frame(node, "w").get("phase") == "halted", msg="沒逾時")
        fr = self.frame(node, "w")
        self.assertEqual((fr["halt"]["kind"], fr["pc"]), ("timeout", "w"), fr)
        self.assertGreater(fr["halt"]["round"] - fr["since"], 2)
        self.assertTrue(fr["accepted"]["a"]["receipt"])
        self.assertEqual(self.ran(node, "w-a"), [])
        open(self.jd(node, "w", "ack"), "w").close()
        self.assertEqual(self.step_cli(node, "resume", "jobs/w").returncode, 0)
        self.run_until(node, "w", lambda: self.frame(node, "w").get("phase") == "ended")
        self.assertEqual(self.step_cli(node, "close", "jobs/w").returncode, 0)
        self.assertFalse(os.path.exists(self.jd(node, "w", "results")))
        self.assertTrue(self.frame(node, "w")["closed"])

    def test_start_wait_patience(self):
        """start 就是 wait（耐性 2）：建框架那圈就有耐性起點，條件不成立照 patience 停在 timeout（A4-03）。"""
        t = {"job": "sw", "start": "w", "steps": {
            "w": {"wait": {"exists": "${job}/never"}, "patience": 2, "then": "done"},
            "done": {"end": "ok"}}}
        node = self.setup_job("sw", t)
        self.run_until(node, "sw", lambda: self.frame(node, "sw").get("phase") == "halted", limit=8, msg="沒逾時")
        fr = self.frame(node, "sw")
        self.assertEqual((fr["halt"]["kind"], fr["pc"]), ("timeout", "w"), fr)
        self.assertIsNotNone(fr["since"])
        self.assertEqual(fr["halt"]["round"] - fr["since"], 3)


if __name__ == "__main__":
    unittest.main()
