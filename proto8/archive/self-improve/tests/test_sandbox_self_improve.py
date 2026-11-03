"""封存 2026-11-03：從 proto8/tests/test_sandbox.py 切出來的案例（原檔其餘照跑）。只作歷史，不在 unittest discover 範圍、不維護；要拉回去跑得併回原檔（用到原檔開頭的常數與小函數）。"""

SELF = str(ROOT / "demo" / "self-improve")
TRY_RUN = str(ROOT / "demo" / "self-improve" / "improver" / "tools" / "try_run" / "_entry")


CHEAT = """#!/usr/bin/env python3
# 偷看判準的函數：照 stdin 去判準檔裡找答案
import json, sys
s = sys.stdin.read()
try:
    cases = json.load(open(%r))
except OSError:
    print("看不到判準"); sys.exit(0)
print(next((c["stdout"] for c in cases if c.get("stdin") == s), ""), end="")
"""


@unittest.skipUnless(HAS_BWRAP, "沒有 bwrap 或這台不給開 user namespace")
class SelfImproveSandboxTest(unittest.TestCase):
    """自我改進的被改函數：原本讀得到判準檔（偷看拿滿分），工作區放了 sandbox.json 就讀不到（零分）。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="test_sandbox_si."))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.ws = self.root / "ws"
        (self.ws / "judge").mkdir(parents=True)
        (self.ws / "target").mkdir()
        cases = [{"stdin": "a", "stdout": "ANSWER-A"}, {"stdin": "b", "stdout": "ANSWER-B", "hidden": True}]
        (self.ws / "judge" / "cases.json").write_text(json.dumps(cases))
        (self.ws / "goal.txt").write_text("把 a 變成 ANSWER-A")
        (self.ws / "budget.json").write_text('{"max_rounds": 0}')            # 只判原版、不改進（不用腦）
        entry = self.ws / "target" / "_entry"
        entry.write_text(CHEAT % str(self.ws / "judge" / "cases.json"))
        entry.chmod(0o755)

    def run_self_improve(self):
        stack = self.root / "stack"
        r = subprocess.run(["aos-exec", "--ws", str(self.ws), SELF], capture_output=True, text=True, timeout=120,
                           env=env(AOS_STACK=str(stack) + "/"))
        verdict = json.loads((stack / "versions" / "v000" / "verdict.json").read_text())
        return r, verdict

    def test_sandbox_false_function_reads_judge(self):
        (self.ws / "sandbox.json").write_text("false")                 # 明寫不關
        r, v = self.run_self_improve()
        self.assertEqual(r.returncode, 0, r.stderr)                     # 偷看就「達成」了
        self.assertEqual((v["score"], v["total"], v["passed"]), (2, 2, True))

    def test_default_boxes_function(self):
        """工作區沒放 sandbox.json＝用 demo/self-improve/sandbox.json 關（10-24 定：預設就關）；外面的 key 也帶不進去。"""
        entry = self.ws / "target" / "_entry"
        entry.write_text((CHEAT % str(self.ws / "judge" / "cases.json")).replace(
            "import json, sys\n", "import json, os, sys\nprint('key=' + os.environ.get('SI_TEST_KEY', 'none'), file=sys.stderr)\n"))
        r = subprocess.run(["aos-exec", "--ws", str(self.ws), SELF], capture_output=True, text=True, timeout=120,
                           env=env(AOS_STACK=str(self.root / "stack") + "/", SI_TEST_KEY="leaked"))
        self.assertEqual(r.returncode, 2, r.stderr)
        runs = [json.loads(x) for x in (self.root / "stack" / "versions" / "v000" / "runs.jsonl").read_text().splitlines()]
        self.assertEqual([x["stdout"] for x in runs], ["看不到判準\n", "看不到判準\n"])
        self.assertTrue(all("key=none" in x["stderr"] for x in runs), runs)

    def test_default_without_bwrap_stops(self):
        """預設要關卻沒有 bwrap：停下說 SandboxMissing，不靜靜改成不關。"""
        stack = self.root / "stack"
        bare = self.root / "bin"
        bare.mkdir()
        for name in ("aos-exec", "aos-loop", "aos-fsm", "python3", "aos-sandbox"):
            os.symlink(shutil.which(name, path=PATH), bare / name)
        r = subprocess.run(["aos-exec", "--ws", str(self.ws), SELF], capture_output=True, text=True, timeout=120,
                           env=env(AOS_STACK=str(stack) + "/", PATH=str(bare)))
        self.assertEqual(r.returncode, 1)
        self.assertIn("self-improve: SandboxMissing", r.stderr)

    def test_with_sandbox_function_cannot_read_judge(self):
        (self.ws / "sandbox.json").write_text(json.dumps(
            {"commands": ["aos-exec"], "rw": [{"$env": "AOS_IMPROVE_RUN"}], "net": False}))
        r, v = self.run_self_improve()
        self.assertEqual(r.returncode, 2, r.stderr)                     # 沒達成、預算 0 輪用完
        self.assertEqual((v["score"], v["passed"]), (0, False))
        runs = [json.loads(x) for x in (self.root / "stack" / "versions" / "v000" / "runs.jsonl").read_text().splitlines()]
        self.assertEqual([x["stdout"] for x in runs], ["看不到判準\n", "看不到判準\n"])

    def test_try_run_is_boxed_too(self):
        """改進者的 try_run 也照 AOS_IMPROVE_SANDBOX 關：同一支函數在 try_run 裡也讀不到判準。"""
        iws = self.root / "iws"
        shutil.copytree(self.ws / "target", iws / "target")
        call = lambda e: subprocess.run([TRY_RUN], input='{"stdin": "a"}', capture_output=True, text=True,
                                        env=env(AOS_WS=str(iws), **e), timeout=60)
        self.assertIn("ANSWER-A", call({}).stdout)
        box = self.root / "box.json"
        box.write_text(json.dumps({"commands": ["aos-exec"], "rw": [{"$env": "AOS_IMPROVE_RUN"}]}))
        out = call({"AOS_IMPROVE_SANDBOX": str(box)}).stdout
        self.assertIn("看不到判準", out)
        self.assertNotIn("ANSWER-A", out)


