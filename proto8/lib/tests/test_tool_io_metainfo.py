"""tool_io.load_tooldef 也讀 _metainfo.json 的 tooldef（11-12 metainfo，N-69）：先裡面、再 _tooldef.json，頂層鍵淺合併、外面贏。"""

import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tool_io

P_IN = {"type": "object", "properties": {"a": {"type": "number"}}}
P_OUT = {"type": "object", "properties": {"b": {"type": "number"}}}


class LoadTooldef(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="tool-io-meta-"))
        tool_io.NAME = "t"

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def write(self, inside=None, outside=None, meta_raw=None):
        if meta_raw is not None:
            (self.d / "_metainfo.json").write_text(meta_raw)
        elif inside is not None:
            (self.d / "_metainfo.json").write_text(json.dumps({"summary": "x", "tooldef": inside}))
        if outside is not None:
            (self.d / "_tooldef.json").write_text(json.dumps(outside))

    def load(self):
        err = io.StringIO()
        with patch.object(sys, "stderr", err):
            return tool_io.load_tooldef(str(self.d)), err.getvalue()

    def test_outside_only(self):
        self.write(outside={"description": "o", "parameters": P_OUT})
        self.assertEqual(self.load(), ({"description": "o", "parameters": P_OUT}, ""))

    def test_inside_only(self):
        self.write(inside={"description": "i", "parameters": P_IN, "positional": ["a"]})
        self.assertEqual(self.load(), ({"description": "i", "parameters": P_IN, "positional": ["a"]}, ""))

    def test_both_outside_wins_per_top_key(self):
        self.write(inside={"description": "i", "parameters": P_IN, "errors": ["X"]},
                   outside={"description": "o", "parameters": P_OUT})
        self.assertEqual(self.load(), ({"description": "o", "parameters": P_OUT, "errors": ["X"]}, ""))

    def test_neither_and_metainfo_without_tooldef(self):
        self.assertEqual(self.load(), (None, ""))
        self.write(meta_raw=json.dumps({"summary": "x"}))
        self.assertEqual(self.load(), (None, ""))

    def test_bad_inside_warns_naming_the_place(self):
        self.write(inside="nope", outside={"parameters": P_OUT})
        td, err = self.load()
        self.assertIsNone(td)
        self.assertIn("_metainfo.json#/tooldef", err)


if __name__ == "__main__":
    unittest.main()
