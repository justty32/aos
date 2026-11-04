"""step 任務包測試。"""
from _step import *  # noqa: F403

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


if __name__ == "__main__":
    unittest.main()
