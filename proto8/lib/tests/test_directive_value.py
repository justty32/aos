"""驗 directive_value：給了 file＝{"$ref": "#/…"} 取那份檔自己；沒給＝原封不動（11-12 ref-hash R1）；resolve_path 一律給設定檔。"""
import json
import os
from pathlib import Path
import shutil
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


if __name__ == "__main__":
    unittest.main()
