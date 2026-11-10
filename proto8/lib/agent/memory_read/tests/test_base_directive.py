"""驗 _memory.json 的 base：舊寫法（相對、絕對字串）照舊，指示詞（$env／$ref）每次用到才解、不寫回，解不開時錯誤行指名檔與欄。"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2]),
                str(Path(__file__).resolve().parents[3])]
import memory_fs  # noqa: E402


@unittest.skipUnless(shutil.which("aos-directive"), "aos-directive not on PATH")
class BaseDirective(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.tool = self.root / "defs" / "ann" / "tools" / "memory_read"
        self.tool.mkdir(parents=True)
        self.kb1 = self.root / "kb1"
        self.kb2 = self.root / "far" / "kb2"
        self.kb1.mkdir()
        self.kb2.mkdir(parents=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ("AOS_CD", "AOS_MEMORY") and not k.startswith("KB_")}

    def write(self, base):
        cfg = self.tool / "_memory.json"
        cfg.write_text(json.dumps({"base": base}))
        return cfg

    def root_of(self, **env):
        with patch.dict(os.environ, dict(self.env, **env), clear=True):
            return memory_fs.memory_root(str(self.tool))

    def fails(self, **env):
        err, out = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, dict(self.env, **env), clear=True), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as cm:
                memory_fs.memory_root(str(self.tool))
        self.assertEqual(cm.exception.code, 1)
        return err.getvalue().strip().splitlines()[-1]

    def test_relative_string_unchanged(self):
        self.write("../../../../kb1")
        self.assertEqual(self.root_of(), str(self.kb1))

    def test_absolute_string_unchanged(self):
        self.write(str(self.kb2))
        self.assertEqual(self.root_of(), str(self.kb2))

    def test_env_directive_follows_variable_and_file_untouched(self):
        cfg = self.write({"$env": "KB_HOME", "$path": "kb1"})
        before = cfg.read_bytes()
        self.assertEqual(self.root_of(KB_HOME=str(self.root)), str(self.kb1))
        self.assertEqual(self.root_of(KB_HOME=str(self.root) + "/"), str(self.kb1))
        self.assertEqual(cfg.read_bytes(), before)
        cfg.write_text(json.dumps({"base": {"$env": "KB_HOME", "$path": "/kb2"}}))   # $path 寫 / 開頭也是接上去（N-45）
        before = cfg.read_bytes()
        self.assertEqual(self.root_of(KB_HOME=str(self.root / "far")), str(self.kb2))
        self.assertEqual(cfg.read_bytes(), before)

    def test_env_change_switches_root(self):
        cfg = self.write({"$env": "KB_DIR"})
        before = cfg.read_bytes()
        self.assertEqual(self.root_of(KB_DIR=str(self.kb1)), str(self.kb1))
        self.assertEqual(self.root_of(KB_DIR=str(self.kb2)), str(self.kb2))
        self.assertEqual(cfg.read_bytes(), before)

    def test_relative_result_from_cfg_folder(self):
        self.write({"$env": "KB_REL"})
        self.assertEqual(self.root_of(KB_REL="../../../../kb1"), str(self.kb1))

    def test_ref_relative_to_cfg_folder(self):
        (self.tool / "where.json").write_text(json.dumps({"kb": str(self.kb2)}))
        self.write({"$ref": "where.json#/kb"})
        self.assertEqual(self.root_of(), str(self.kb2))

    def test_env_unset_names_file_and_field(self):
        cfg = self.write({"$env": "KB_UNSET", "$path": "kb1"})
        line = self.fails()
        self.assertTrue(line.startswith("tool: error: CfgBad "), line)
        self.assertIn(str(cfg), line)
        self.assertIn('base {"$env": "KB_UNSET", "$path": "kb1"}', line)
        self.assertIn("cannot be resolved", line)

    def test_resolves_to_non_string(self):
        (self.tool / "where.json").write_text(json.dumps({"kb": {"a": 1}}))
        cfg = self.write({"$ref": "where.json#/kb"})
        line = self.fails()
        self.assertIn("error: CfgBad %s: base" % cfg, line)
        self.assertIn('resolves to {"a": 1}', line)

    def test_resolves_to_missing_folder(self):
        cfg = self.write({"$env": "KB_HOME", "$path": "nope"})
        line = self.fails(KB_HOME=str(self.root))
        self.assertIn("error: MemoryBad %s base " % cfg, line)
        self.assertIn(str(self.root / "nope"), line)

    def test_directive_tool_missing(self):
        self.write({"$env": "KB_HOME"})
        empty = self.root / "emptybin"
        empty.mkdir()
        line = self.fails(KB_HOME=str(self.kb1), PATH=str(empty))
        self.assertIn("error: CommandMissing ", line)
        self.assertIn("aos-directive", line)

    def test_other_bad_types_keep_old_message(self):
        cfg = self.write(5)
        self.assertEqual(self.fails(), "tool: error: CfgBad %s must be an object with a non-empty string key base" % cfg)


if __name__ == "__main__":
    unittest.main()
