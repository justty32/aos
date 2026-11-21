"""Test where aos.hook_point finds a definition's hook files: "hooks" and "hookeds" at the top of interfaces.json (a file name, a directive, or an array of them), the stack's copies (layers, own), and every template saying them the new way."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
PY = Path(__file__).resolve().parents[1]
ROOT = PY.parent
sys.path.insert(0, str(PY))
from aos import hook_lists, hook_point


class Items(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = os.path.realpath(self.tmp.name)

    def face(self, doc):
        with open(os.path.join(self.d, "interfaces.json"), "w", encoding="utf-8") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))

    def test_nothing(self):
        self.assertEqual(hook_point.items(self.d, "hookeds"), [])
        self.face({"aos-agent": {}})
        self.assertEqual(hook_point.files(self.d, "hooks"), [])
        self.assertEqual(hook_point.layers(self.d, "/st"), [])
        self.assertIsNone(hook_point.own(self.d, "/st"))

    def test_string_and_array(self):
        self.face({"hooks": ["a.json", "/abs/b.json"], "hookeds": "hookeds.json"})
        self.assertEqual(hook_point.files(self.d, "hooks"), [os.path.join(self.d, "a.json"), "/abs/b.json"])
        self.assertEqual(hook_point.layers(self.d, "/st"), [os.path.join(self.d, "hookeds.json"), "/st/hookeds.json"])
        self.assertEqual(hook_point.layers(self.d), [os.path.join(self.d, "hookeds.json")])
        self.assertEqual(hook_point.own(self.d, "/st"), "/st/hookeds.json")

    def test_only_relative_items_get_a_stack_copy(self):
        self.face({"hookeds": ["/abs/shared.json", "mine.json", "../up.json", "more.json"]})
        self.assertEqual(hook_point.layers(self.d, "/st"),
                         ["/abs/shared.json", os.path.join(self.d, "mine.json"), os.path.join(self.d, "../up.json"),
                          os.path.join(self.d, "more.json"), "/st/mine.json", "/st/more.json"])
        self.assertEqual(hook_point.own(self.d, "/st"), "/st/mine.json")

    @unittest.skipUnless(shutil.which("aos-directive"), "aos-directive not on PATH")
    def test_directives(self):
        self.face({"where": "x.json", "hooks": [{"$env": "HP_TEST", "$path": "/loop.json"}, {"$ref": "#/where"}],
                   "hookeds": {"$env": "HP_TEST", "$path": "/hk.json"}})
        with mock.patch.dict(os.environ, {"HP_TEST": "/home/x"}):
            self.assertEqual(hook_point.files(self.d, "hooks"), ["/home/x/loop.json", os.path.join(self.d, "x.json")])
            self.assertEqual(hook_point.layers(self.d, "/st"), ["/home/x/hk.json"])   # a directive has no stack copy
            self.assertIsNone(hook_point.own(self.d, "/st"))
        env = {k: v for k, v in os.environ.items() if k != "HP_TEST"}
        with mock.patch.dict(os.environ, env, clear=True), self.assertRaises(hook_point.InterfaceBad) as cm:
            hook_point.files(self.d, "hooks")
        self.assertIn("hooks[0] cannot be resolved", str(cm.exception))

    def test_bad(self):
        for doc, word in (("{", "cannot read"), ("[]", "must be a JSON object"),
                          ({"hookeds": {"description": "x", "a": {"event": "e", "handler": "h"}}}, "must be a file name"),
                          ({"hookeds": 3}, "must be a file name"), ({"hookeds": ["a.json", ""]}, "hookeds[1] must be a file name")):
            with self.subTest(doc=doc):
                self.face(doc)
                with self.assertRaises(hook_point.InterfaceBad) as cm:
                    hook_point.items(self.d, "hookeds")
                self.assertIn(word, str(cm.exception))


class Templates(unittest.TestCase):
    """The two keys moved to the top: no definition says them inside aos-agent any more, and each points at the right kind of file."""

    def faces(self):
        for path in sorted(ROOT.glob("templates/**/interfaces.json")) + sorted(ROOT.glob("frontend/**/interfaces.json")):
            yield path, json.loads(path.read_text(encoding="utf-8"))

    def test_no_hook_keys_inside_aos_agent(self):
        for path, doc in self.faces():
            with self.subTest(path=str(path)):
                self.assertFalse({"hooks", "hookeds", "hook_points"} & set(doc.get("aos-agent", {})))

    def test_hooks_are_declarations_and_hookeds_are_lists(self):
        """The trap of the swap: a file named by "hooks" must be a declaration, one named by "hookeds" a list."""
        home = {"AOS_HOME": str(ROOT)}
        seen = 0
        for path, doc in self.faces():
            if "hooks" not in doc:
                continue
            seen += 1
            with self.subTest(path=str(path)), mock.patch.dict(os.environ, home):
                decl = [p.replace(os.path.join(str(ROOT), "lib"), str(PY)) for p in hook_point.files(str(path.parent), "hooks")]
                points = hook_point.read(decl)
                self.assertTrue(points)
                for p in hook_point.files(str(path.parent), "hookeds"):
                    if os.path.exists(p):
                        hook_lists.read(p)
                        with open(p, encoding="utf-8") as f:
                            self.assertNotIn("hooks", json.load(f))
        self.assertGreaterEqual(seen, 12)

    def test_no_list_file_has_the_old_names(self):
        for old in ("hook_points.json", "loop_points.json"):
            self.assertEqual([str(p) for p in ROOT.glob("templates/**/" + old)], [])
        for name in ("hooks.json",):
            for p in ROOT.glob("templates/**/" + name):
                with self.subTest(path=str(p)):
                    hook_point.read([str(p)])          # a hooks.json is a declaration, never a list


if __name__ == "__main__":
    unittest.main()
