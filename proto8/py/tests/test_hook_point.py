"""Test aos.hook_point's declarations: every shipped hook point declaration reads (an object of ids, each with an input schema), the few rules, and that the ones aos ships say what the code fires."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PY = Path(__file__).resolve().parents[1]
ROOT = PY.parent
sys.path.insert(0, str(PY))
from aos import hook_point
from aos.hook_point import PointsBad

SHIPPED = {"loop": PY / "aos" / "apps" / "hook" / "loop_hooks.json",
           "agent-fsm": PY / "aos" / "apps" / "agent_fsm" / "hooks.json",
           "eca": PY / "aos" / "apps" / "eca" / "hooks.json",
           "mcp": PY / "aos" / "apps" / "mcp" / "hooks.json",
           "kernel": PY / "tools" / "aos" / "kernel" / "kernel_hooks.json"}


class Shipped(unittest.TestCase):
    def test_each_file_reads(self):
        for name, path in SHIPPED.items():
            with self.subTest(name=name):
                points = hook_point.read([str(path)])
                self.assertTrue(points)
                for pid, p in points.items():
                    self.assertEqual(p["input"].get("type"), "object", (name, pid))
                    self.assertTrue(p.get("description"), (name, pid))

    def test_fired_in_files_exist_and_name_the_point(self):
        """fired_in (a free key the shipped declarations keep) names the files that fire the point."""
        for name, path in SHIPPED.items():
            for pid, p in hook_point.read([str(path)]).items():
                for f in p.get("fired_in", []):
                    with self.subTest(point=pid, file=f):
                        text = (path.parent / f).read_text(encoding="utf-8")
                        self.assertIn(pid, text)

    def test_kernel_copies_match_the_canonical_one(self):
        canon = json.loads(SHIPPED["kernel"].read_text(encoding="utf-8"))
        copies = sorted(ROOT.glob("templates/**/kernel_hooks.json"))
        self.assertGreaterEqual(len(copies), 7)
        for c in copies:
            with self.subTest(copy=str(c)):
                self.assertEqual(json.loads(c.read_text(encoding="utf-8")), canon)


class Rules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.n = 0

    def file(self, doc):
        self.n += 1
        path = os.path.join(self.tmp.name, "h%d.json" % self.n)
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return path

    def test_good_minimal_and_free_keys(self):
        got = hook_point.read([self.file({"description": "x", "a_b": {"input": {}, "block": "yes", "whatever": [1]}})])
        self.assertEqual(got, {"a_b": {"input": {}, "block": "yes", "whatever": [1]}})

    def test_first_one_counts(self):
        a = self.file({"p": {"input": {"title": "first"}}})
        b = self.file({"p": {"input": {"title": "second"}}, "q": {"input": {}}})
        got = hook_point.read([a, b])
        self.assertEqual(got["p"]["input"]["title"], "first")
        self.assertEqual(sorted(got), ["p", "q"])

    def test_bad(self):
        cases = (("[1]", "must be a JSON object"), ("{", "cannot read hook points"),
                 ({"Bad": {"input": {}}}, "may only have a-z, 0-9 and _"),
                 ({"p": {"description": "no input"}}, "must be an object with input"),
                 ({"p": {"input": "x"}}, "must be an object with input"), ({"p": 3}, "must be an object with input"))
        for doc, word in cases:
            with self.subTest(doc=doc):
                with self.assertRaises(PointsBad) as cm:
                    hook_point.read([self.file(doc)])
                self.assertIn(word, str(cm.exception))
        with self.assertRaises(PointsBad):
            hook_point.read([os.path.join(self.tmp.name, "missing.json")])


if __name__ == "__main__":
    unittest.main()
