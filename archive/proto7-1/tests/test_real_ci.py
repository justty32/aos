"""真模型場景的 ci 機器人（demo/real_scene/team/agents/ci/ci.py）：不測不回非程式碼、重複的程式碼，PASS 時 CC 負責人（R-6、R-7、R-14）。"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "lib"))
CI_DIR = os.path.join(BASE, "demo", "real_scene", "team", "agents", "ci")

GOOD_DUR = '''import re
U = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]


def parse_duration(s):
    if not isinstance(s, str):
        raise ValueError(s)
    t = s.strip().lower()
    m = re.fullmatch(r"(?:(0|[1-9]\\d*)d)?(?:(0|[1-9]\\d*)h)?(?:(0|[1-9]\\d*)m)?(?:(0|[1-9]\\d*)s)?", t)
    if not t or not m:
        raise ValueError(s)
    return sum(int(g) * v for g, (_, v) in zip(m.groups(), U) if g)


def format_duration(n):
    if type(n) is not int or n < 0:
        raise ValueError(n)
    if n == 0:
        return "0s"
    out = ""
    for u, v in U:
        q, n = divmod(n, v)
        if q:
            out += "%d%s" % (q, u)
    return out
'''


def load_ci():
    spec = importlib.util.spec_from_file_location("real_ci", os.path.join(CI_DIR, "ci.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RealCi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="aos7-test-ci-")
        node = os.path.join(self.tmp, "ci")
        shutil.copytree(CI_DIR, node)
        self.ctx = {"node": node}
        self.ci = load_ci()
        self.sent = []
        self.ci.tools = mock.Mock(do_tool=lambda ctx, step, rnd: self.sent.append((step["to"], step["body"])) or "sent")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_skip_not_code_and_duplicates_cc_pass(self):
        st = {"n": 0}
        r = self.ci.handle(self.ctx, st, {"from": "t/lead", "body": "工作已完成，謝謝"}, 1, ["t/lead"])
        self.assertEqual((r["kind"], self.sent), ("not_code", []))   # 不測、不回：不會變成 lead 的一封新信
        r = self.ci.handle(self.ctx, st, {"from": "t/coder", "body": "```python\n%s```" % GOOD_DUR}, 2, ["t/lead"])
        self.assertEqual((r["kind"], r["module"], r["passed"], r["total"]), ("test", "dur", 36, 36))
        self.assertEqual([to for to, _ in self.sent], ["t/coder", "t/lead"])   # PASS 也寄給負責人，附程式碼
        self.assertIn("def parse_duration", self.sent[1][1])
        import aos7_agent_tools   # 附的程式碼包在 ``` 裡，lead 的 save code: true 取得到原文（R-15 (b)）
        self.assertEqual(aos7_agent_tools.extract_code(self.sent[1][1]).strip(), GOOD_DUR.strip())
        r = self.ci.handle(self.ctx, st, {"from": "t/coder", "body": GOOD_DUR}, 3, ["t/lead"])
        self.assertEqual((r["kind"], r["n"], len(self.sent)), ("dup", 1, 2))   # 一樣的程式碼：不測、不回
        self.assertEqual(st["n"], 1)

    def test_unknown_module_fails_clearly(self):
        st = {"n": 0}
        r = self.ci.handle(self.ctx, st, {"from": "t/coder", "body": "def merge_ranges(x):\n    return x\n"}, 1, ["t/lead"])
        self.assertEqual((r["kind"], r["module"], r["passed"]), ("test", "?", 0))
        self.assertEqual([to for to, _ in self.sent], ["t/coder"])   # FAIL 不 CC
        self.assertIn("看不出是哪個模組", self.sent[0][1])


    def test_ci_version_of_final_file(self):
        """R-15：real.py 認得出 lead 交的檔是 ci 測過的哪一版；自己重打過的認不出。"""
        sys.path.insert(0, os.path.join(BASE, "demo"))
        import real
        from aos7_fs import write_json
        runs = os.path.join(self.tmp, "team", "agents", "ci", "work", "runs")
        for n, code in ((1, "def parse_duration(s):\n    pass\n"), (2, GOOD_DUR)):
            os.makedirs(os.path.join(runs, str(n)))
            with open(os.path.join(runs, str(n), "dur.py"), "w") as f:
                f.write(code)
            write_json(os.path.join(runs, str(n), "result.json"), {"passed": n, "total": 36})
        final = os.path.join(self.tmp, "dur.py")
        with open(final, "w") as f:
            f.write("\n" + GOOD_DUR + "\n\n")
        self.assertEqual(real.ci_version_of(self.tmp, final), (2, {"passed": 2, "total": 36}))
        with open(final, "w") as f:
            f.write(GOOD_DUR.replace("    out = \"\"", "    out = ''"))
        self.assertIsNone(real.ci_version_of(self.tmp, final))


if __name__ == "__main__":
    unittest.main()
