"""index_view 對 index 一項裡多出來的鍵（timeout_ms、自訂鍵…）照常印「名<TAB>description」、不報錯：index 的格都只是參考（使用者 11-12 晚）。"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1]
IMPLS = LIB.parent / "impls"
TOOL = LIB / "base" / "index_view" / "_entry"


class IndexExtraKeysTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        self.env = dict(os.environ, AOS_WS=str(self.ws))
        self.env.pop("AOS_JSON_MAX_ITEMS", None)
        self.env["PATH"] = "%s:%s" % (IMPLS / "aos-json/bin", self.env.get("PATH", ""))

    def view(self, **args):
        r = subprocess.run([str(TOOL)], input=json.dumps(args), text=True, capture_output=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout.rstrip("\n").split("\n")

    def test_extra_keys_in_folder_index(self):
        (self.ws / "kb").mkdir()
        (self.ws / "kb" / "_index.json").write_text(json.dumps(
            {"a": {"description": "x", "timeout_ms": 5, "whatever": [1]}}))
        self.assertEqual(self.view(path="kb"), ["[index] kb/_index.json, 1 entry", "a\tx"])

    def test_extra_keys_in_embedded_index(self):
        (self.ws / "cfg.json").write_text(json.dumps(
            {"_index": {"a": {"description": "x", "cost": {"time_ms": "soon"}, "whatever": [1]}}, "a": 1}))
        self.assertEqual(self.view(path="cfg.json")[1:], ["a\tx"])


if __name__ == "__main__":
    unittest.main()
