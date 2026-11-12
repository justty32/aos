"""驗 cli.json 的 tools：舊寫法（相對、絕對字串）照舊，指示詞（$env／$ref）每次讀才解、不寫回，解不開時錯誤行指名檔與欄。"""
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
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent import cli_cfg  # noqa: E402


@unittest.skipUnless(shutil.which("aos-directive"), "aos-directive not on PATH")
class ToolsDirective(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.tool = self.root / "defs" / "eca" / "tools" / "claude"
        self.tool.mkdir(parents=True)
        self.reg1 = self.root / "shared" / "tools.json"
        self.reg2 = self.root / "other" / "tools.json"
        for r in (self.reg1, self.reg2):
            r.parent.mkdir(parents=True)
            r.write_text('{"tools": {}}\n')
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and not k.startswith("REG_")}

    def write(self, tools):
        cfg = self.tool / "cli.json"
        cfg.write_text(json.dumps({"kind": "claude", "tools": tools}))
        return cfg

    def registry(self, **env):
        with patch.dict(os.environ, dict(self.env, **env), clear=True):
            return cli_cfg.load_cfg(str(self.tool))["registry"]

    def fails(self, **env):
        err = io.StringIO()
        with patch.dict(os.environ, dict(self.env, **env), clear=True), contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                cli_cfg.load_cfg(str(self.tool))
        self.assertEqual(cm.exception.code, 1)
        return err.getvalue().strip().splitlines()[-1]

    def test_relative_string_unchanged(self):
        self.write("../../../../shared/tools.json")
        self.assertEqual(self.registry(), str(self.reg1))

    def test_absolute_string_unchanged(self):
        self.write(str(self.reg2))
        self.assertEqual(self.registry(), str(self.reg2))

    def test_env_directive_follows_variable_and_file_untouched(self):
        cfg = self.write({"$env": "REG_HOME", "$path": "tools.json"})
        before = cfg.read_bytes()
        self.assertEqual(self.registry(REG_HOME=str(self.reg1.parent)), str(self.reg1))
        self.assertEqual(self.registry(REG_HOME=str(self.reg2.parent)), str(self.reg2))
        self.assertEqual(cfg.read_bytes(), before)

    def test_relative_result_from_cli_json_folder(self):
        self.write({"$env": "REG_REL"})
        self.assertEqual(self.registry(REG_REL="../../../../other/tools.json"), str(self.reg2))

    def test_ref_relative_to_cli_json_folder(self):
        (self.tool / "where.json").write_text(json.dumps({"reg": str(self.reg1)}))
        self.write({"$ref": "where.json#/reg"})
        self.assertEqual(self.registry(), str(self.reg1))

    def test_ref_hash_takes_cli_json_itself(self):
        """11-12 ref-hash：{"$ref": "#/…"}（沒檔名）＝cli.json 自己。"""
        cfg = self.tool / "cli.json"
        cfg.write_text(json.dumps({"kind": "claude", "paths": {"reg": str(self.reg2)}, "tools": {"$ref": "#/paths/reg"}}))
        self.assertEqual(self.registry(), str(self.reg2))

    def test_env_unset_names_file_and_field(self):
        cfg = self.write({"$env": "REG_UNSET", "$path": "tools.json"})
        line = self.fails()
        self.assertTrue(line.startswith("cli_session: error: CfgBad %s: tools " % cfg), line)
        self.assertIn('{"$env": "REG_UNSET", "$path": "tools.json"} cannot be resolved', line)

    def test_resolves_to_non_string(self):
        (self.tool / "where.json").write_text(json.dumps({"reg": [1]}))
        cfg = self.write({"$ref": "where.json#/reg"})
        line = self.fails()
        self.assertIn("error: CfgBad %s: tools " % cfg, line)
        self.assertIn("resolves to [1]", line)

    def test_resolves_to_missing_file(self):
        cfg = self.write({"$env": "REG_HOME", "$path": "nope.json"})
        line = self.fails(REG_HOME=str(self.root))
        self.assertEqual(line, "cli_session: error: ToolsMissing %s: registry file named by tools not found: %s" % (cfg, self.root / "nope.json"))

    def test_directive_tool_missing(self):
        self.write({"$env": "REG_HOME"})
        empty = self.root / "emptybin"
        empty.mkdir()
        line = self.fails(REG_HOME=str(self.reg1), PATH=str(empty))
        self.assertIn("error: CommandMissing ", line)
        self.assertIn("aos-directive", line)

    def test_other_bad_types_keep_old_message(self):
        cfg = self.write(5)
        self.assertEqual(self.fails(), "cli_session: error: CfgBad %s: tools must be the path of a registry file (a non-empty string)" % cfg)


if __name__ == "__main__":
    unittest.main()
