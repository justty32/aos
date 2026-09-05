"""aosp/loader.py：原稿 -> 模板，壞原稿要丟 ParseError 且訊息指路。"""
import os
import sys

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import fsutil, loader  # noqa: E402
from .helpers import LandCase, write_source  # noqa: E402


class TestCompileGood(LandCase):
    def test_good_source_compiles_to_program_file(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": ["echo", "hi"]}, "then": "end"},
        ])
        loader.compile_source(self.land, "main")
        self.assertTrue(os.path.isfile(self.land.program("main")),
                         msg="模板應該落在 .aos/program/main.json：%s" % self.land.program("main"))
        on_disk = fsutil.read_json(self.land.program("main"))
        self.assertEqual(on_disk["steps"][0]["name"], "s1",
                          msg="落地的模板內容應該跟原稿一致，實際 %r" % on_disk)

    def test_load_program_auto_compiles(self):
        write_source(self.land, [
            {"name": "only", "kind": "inst", "inst": {"argv": ["echo", "x"]}, "then": "end"},
        ])
        self.assertFalse(os.path.isfile(self.land.program("main")),
                          msg="還沒編譯過，不該有模板檔")
        prog = loader.load_program(self.land, "main")
        self.assertEqual(prog["steps"][0]["name"], "only")
        self.assertTrue(os.path.isfile(self.land.program("main")),
                         msg="load_program 應該在沒有模板時自動編譯出一份")


class TestParseErrorsFromCheck(LandCase):
    """直接測 check_program：確認錯誤訊息指路（欄位名要出現在訊息裡）。"""

    def _expect(self, prog, must_contain):
        with self.assertRaises(loader.ParseError) as ctx:
            loader.check_program(prog)
        msg = str(ctx.exception)
        self.assertIn(must_contain, msg,
                      msg="錯誤訊息應該指出是哪個欄位／哪一步出問題，實際訊息是 %r，該包含 %r"
                      % (msg, must_contain))

    def test_missing_format_version(self):
        self._expect({"name": "main", "steps": [
            {"name": "s1", "kind": "inst", "inst": {"argv": ["echo"]}},
        ]}, "format_version")

    def test_unknown_kind(self):
        self._expect({"format_version": 1, "name": "main", "steps": [
            {"name": "s1", "kind": "frobnicate"},
        ]}, "kind")

    def test_duplicate_step_name(self):
        self._expect({"format_version": 1, "name": "main", "steps": [
            {"name": "dup", "kind": "inst", "inst": {"argv": ["echo"]}},
            {"name": "dup", "kind": "inst", "inst": {"argv": ["echo"]}},
        ]}, "dup")

    def test_then_points_to_missing_step(self):
        self._expect({"format_version": 1, "name": "main", "steps": [
            {"name": "s1", "kind": "inst", "inst": {"argv": ["echo"]}, "then": "does-not-exist"},
        ]}, "then")

    def test_on_fail_points_to_missing_step(self):
        self._expect({"format_version": 1, "name": "main", "steps": [
            {"name": "s1", "kind": "inst", "inst": {"argv": ["echo"]}, "on_fail": "nope"},
        ]}, "on_fail")

    def test_missing_steps_key(self):
        self._expect({"format_version": 1, "name": "main"}, "steps")

    def test_missing_argv_on_inst(self):
        self._expect({"format_version": 1, "name": "main", "steps": [
            {"name": "s1", "kind": "inst", "inst": {}},
        ]}, "argv")


class TestParseErrorsFromCompileSource(LandCase):
    """再確認整條路：write_source -> compile_source 一樣會擋下來、訊息一樣指路。"""

    def test_compile_source_raises_on_bad_source(self):
        write_source(self.land, [
            {"name": "dup", "kind": "inst", "inst": {"argv": ["echo"]}},
            {"name": "dup", "kind": "inst", "inst": {"argv": ["echo"]}},
        ])
        with self.assertRaises(loader.ParseError) as ctx:
            loader.compile_source(self.land, "main")
        self.assertIn("dup", str(ctx.exception),
                      msg="compile_source 對壞原稿也該丟 ParseError 且訊息指出步名，實際 %r"
                      % str(ctx.exception))
        self.assertFalse(os.path.isfile(self.land.program("main")),
                          msg="解析失敗不該留下（或更新）模板檔")

    def test_compile_source_missing_file(self):
        with self.assertRaises(loader.ParseError):
            loader.compile_source(self.land, "no-such-source")
