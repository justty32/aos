"""驗 directive_value：給了 file＝{"$ref": "#/…"} 取那份檔自己；沒給＝原封不動（11-12 ref-hash R1）；resolve_path 一律給設定檔。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import directive_value  # noqa: E402


@unittest.skipUnless(shutil.which("aos-directive"), "aos-directive not on PATH")
class RefHash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.cfg = self.root / "cfg.json"
        self.cfg.write_text(json.dumps({"defs": {"p": "sub/x.json"}, "use": {"$ref": "#/defs/p"}}))

    def test_file_given_takes_the_file_itself(self):
        self.assertEqual(directive_value.resolve({"$ref": "#/defs/p"}, str(self.root), str(self.cfg)), "sub/x.json")

    def test_no_file_left_as_written(self):
        self.assertEqual(directive_value.resolve({"$ref": "#/defs/p"}, str(self.root)), {"$ref": "#/defs/p"})

    def test_resolve_path_gives_the_cfg_file(self):
        self.assertEqual(directive_value.resolve_path({"$ref": "#/defs/p"}, str(self.cfg), "use"), "sub/x.json")

    def test_relative_ref_still_from_cwd(self):
        (self.root / "o.json").write_text(json.dumps({"k": "v"}))
        self.assertEqual(directive_value.resolve({"$ref": "o.json#/k"}, str(self.root), str(self.cfg)), "v")


@unittest.skipUnless(shutil.which("aos-directive"), "aos-directive not on PATH")
class ErrorDetail(unittest.TestCase):
    def test_pipe_keeps_stderr_and_exit_code(self):
        env = dict(os.environ)
        env.pop("AOS_TEST_NOPE_XYZ", None)
        with self.assertRaises(directive_value.Error) as got:
            directive_value.resolve({"$env": "AOS_TEST_NOPE_XYZ"}, tempfile.gettempdir(), stderr=subprocess.PIPE)
        e = got.exception
        self.assertEqual((e.code, e.returncode, e.cause), ("DirectiveBad", 1, None))
        self.assertIn("aos-directive: error: DirectiveBad", e.stderr)

    def test_missing_command_keeps_the_os_error(self):
        old = os.environ["PATH"]
        os.environ["PATH"] = tempfile.gettempdir() + "/aos-test-no-such-dir"
        try:
            with self.assertRaises(directive_value.Error) as got:
                directive_value.resolve({"$env": "HOME"}, tempfile.gettempdir())
        finally:
            os.environ["PATH"] = old
        self.assertEqual(got.exception.code, "CommandMissing")
        self.assertIsInstance(got.exception.cause, OSError)


@unittest.skipUnless(shutil.which("aos-directive"), "aos-directive not on PATH")
class At(unittest.TestCase):
    """11-13 線址二：給了 at＝#./、#../ 從這格所在的物件算（aos-directive --at）；沒給＝跟以前一樣。"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.cfg = self.root / "cfg.json"
        self.cfg.write_text(json.dumps({"x": "top", "a": {"x": "in-a", "b": {"$ref": "#./x"}, "c": {"$ref": "#../x"}}}))

    def test_dot_counts_from_the_object_it_sits_in(self):
        got = directive_value.resolve({"$ref": "#./x"}, str(self.root), str(self.cfg), at=directive_value.pointer("a", "b"))
        self.assertEqual(got, "in-a")

    def test_dotdot_counts_one_level_up(self):
        got = directive_value.resolve({"$ref": "#../x"}, str(self.root), str(self.cfg), at=directive_value.pointer("a", "c"))
        self.assertEqual(got, "top")

    def test_resolve_path_passes_at(self):
        self.assertEqual(directive_value.resolve_path({"$ref": "#./x"}, str(self.cfg), "a.b", at="/a/b"), "in-a")

    def test_no_at_is_unchanged_whole_file(self):
        """沒給 at＝當它是整份檔：#./ 沒有所在物件＝報錯（跟改之前一樣）。"""
        with self.assertRaises(directive_value.Error):
            directive_value.resolve_path({"$ref": "#./x"}, str(self.cfg), "a.b")
        self.assertEqual(directive_value.resolve({"$ref": "#/a/x"}, str(self.root), str(self.cfg)), "in-a")

    def test_at_without_file_is_ignored(self):
        self.assertEqual(directive_value.resolve({"$ref": "#./x"}, str(self.root), at="/a/b"), {"$ref": "#./x"})

    def test_pointer_escapes(self):
        self.assertEqual(directive_value.pointer("a~b", "c/d", 3), "/a~0b/c~1d/3")
        self.assertEqual(directive_value.pointer(), "")


if __name__ == "__main__":
    unittest.main()
