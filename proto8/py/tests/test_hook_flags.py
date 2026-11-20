"""Test aos.hook_flags.sync: the before_run / after_run flag files follow the hooks in effect, only for declared loop points, and are written whole (no temp file left)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aos import hook_flags

LOOP = {"before_run": {}, "after_run": {}, "after_start": {}}


class Sync(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="hook-flags-")
        self.addCleanup(tmp.cleanup)
        self.stack = tmp.name

    def flag(self, point):
        return os.path.join(self.stack, hook_flags.FLAGS[point])

    def test_on_and_off(self):
        got = hook_flags.sync(self.stack, LOOP, {"a": {"event": "before_run"}, "b": {"event": "after_tool"}})
        self.assertEqual(got, {"before_run": True, "after_run": False})
        self.assertTrue(os.path.isfile(self.flag("before_run")))
        self.assertFalse(os.path.exists(self.flag("after_run")))
        self.assertIn("on_before_run", Path(self.flag("before_run")).read_text())
        self.assertEqual(sorted(os.listdir(self.stack)), [hook_flags.FLAGS["before_run"]])   # no temp file left
        got = hook_flags.sync(self.stack, LOOP, {"c": {"event": "after_run"}})
        self.assertEqual(got, {"before_run": False, "after_run": True})
        self.assertFalse(os.path.exists(self.flag("before_run")))
        self.assertTrue(os.path.isfile(self.flag("after_run")))
        self.assertEqual(hook_flags.sync(self.stack, LOOP, {}), {"before_run": False, "after_run": False})
        self.assertEqual(os.listdir(self.stack), [])

    def test_undeclared_points_left_alone(self):
        Path(self.flag("before_run")).write_text("x\n")
        self.assertEqual(hook_flags.sync(self.stack, {"after_run": {}}, {}), {"after_run": False})
        self.assertTrue(os.path.isfile(self.flag("before_run")))   # not declared here: not ours to judge
        self.assertEqual(hook_flags.sync(self.stack, {"before_tool": {}}, {"a": {"event": "before_run"}}), {})

    def test_existing_flag_kept_as_is(self):
        Path(self.flag("after_run")).write_text("hand made\n")
        hook_flags.sync(self.stack, LOOP, {"a": {"event": "after_run"}})
        self.assertEqual(Path(self.flag("after_run")).read_text(), "hand made\n")

    def test_cannot_write(self):
        with self.assertRaises(OSError):
            hook_flags.sync(os.path.join(self.stack, "missing"), LOOP, {"a": {"event": "before_run"}})


if __name__ == "__main__":
    unittest.main()
