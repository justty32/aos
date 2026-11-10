"""Test lib/agent/copy_def.Rewriter on a fake proto8: string values, AOS_CD directives, symlinks per mode, and env-mode symlink fallbacks."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent import copy_def  # noqa: E402


class RewriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="copy-def-"))
        self.proto = self.tmp / "proto8"
        (self.proto / "lib" / "t").mkdir(parents=True)
        (self.proto / "lib" / "t" / "_entry").write_text("#!/bin/sh\n")
        (self.proto / "lib" / "t" / "data.json").write_text('{"x": 1}\n')
        self.src = self.proto / "templates" / "tpl"
        (self.src / "sub").mkdir(parents=True)
        (self.src / "tools.json").write_text(json.dumps({"tools": {"t": {"path": "../../lib/t"}, "in": {"path": "sub"}},
                                                           "note": "a/b", "abs": "/etc/x"}))
        (self.src / "sub" / "conf.json").write_text(json.dumps({"argv": [{"$env": "AOS_CD", "$path": "../../lib/t/_entry"},
                                                                         {"$env": "AOS_WS", "$path": "../../lib/t"}]}))
        os.symlink("../../../lib/t/_entry", self.src / "sub" / "_entry")
        os.symlink("../../../lib/t/data.json", self.src / "sub" / "data.json")
        os.symlink("../../lib/t", self.src / "tdir")
        self.warnings = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def copy(self, mode):
        dest = self.tmp / ("out-" + mode)
        shutil.copytree(self.src, dest, symlinks=True)
        n = copy_def.Rewriter(self.src, dest, dest, mode, warn=self.warnings.append, proto=str(self.proto)).run()
        return dest, n

    def read(self, *parts):
        return json.loads(Path(*parts).read_text())

    def test_env(self):
        dest, n = self.copy("env")
        tools = self.read(dest, "tools.json")
        self.assertEqual(tools["tools"]["t"]["path"], {"$env": "AOS_HOME", "$path": "/lib/t"})
        self.assertEqual(tools["tools"]["in"]["path"], "sub")
        self.assertEqual(tools["note"], "a/b")
        self.assertEqual(tools["abs"], "/etc/x")
        conf = self.read(dest, "sub", "conf.json")
        self.assertEqual(conf["argv"][0], {"$env": "AOS_HOME", "$path": "/lib/t/_entry"})
        self.assertEqual(conf["argv"][1], {"$env": "AOS_WS", "$path": "../../lib/t"})       # 別的指示詞不動
        self.assertEqual(self.read(dest, "sub", "_entry"), {"argv": ["aos-exec", {"$env": "AOS_HOME", "$path": "/lib/t/_entry"}]})
        self.assertFalse((dest / "sub" / "data.json").is_symlink())
        self.assertEqual(self.read(dest, "sub", "data.json"), {"x": 1})
        self.assertEqual(os.readlink(dest / "tdir"), str(self.proto / "lib" / "t"))
        self.assertEqual(len([w for w in self.warnings if "cannot hold AOS_HOME" in w]), 2)

    def test_absolute(self):
        dest, _ = self.copy("absolute")
        self.assertEqual(self.read(dest, "tools.json")["tools"]["t"]["path"], str(self.proto / "lib" / "t"))
        self.assertEqual(self.read(dest, "sub", "conf.json")["argv"][0], str(self.proto / "lib" / "t" / "_entry"))
        self.assertEqual(os.readlink(dest / "sub" / "_entry"), str(self.proto / "lib" / "t" / "_entry"))

    def test_relative(self):
        dest, _ = self.copy("relative")
        p = self.read(dest, "tools.json")["tools"]["t"]["path"]
        self.assertEqual(os.path.realpath(dest / p), str(self.proto / "lib" / "t"))
        cd = self.read(dest, "sub", "conf.json")["argv"][0]
        self.assertEqual(cd["$env"], "AOS_CD")
        self.assertEqual(os.path.realpath(dest / cd["$path"]), str(self.proto / "lib" / "t" / "_entry"))
        self.assertTrue((dest / "sub" / "_entry").exists())

    def test_source_untouched_and_bad_mode(self):
        before = (self.src / "tools.json").read_text()
        self.copy("env")
        self.assertEqual((self.src / "tools.json").read_text(), before)
        with self.assertRaises(copy_def.CopyFail):
            copy_def.Rewriter(self.src, self.tmp, self.tmp, "weird")


if __name__ == "__main__":
    unittest.main()
