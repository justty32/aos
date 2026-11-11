"""驗 cli_session 的 system（11-11 self-system）：宣告了才碰；stack 那份在就整份用它、否則定義那份；claude 附加檔＋snapshot off、codex developer_instructions；空＝不附加。"""
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
from agent import cli_session  # noqa: E402


class CliSystem(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cli-system-"))
        self.defn = self.tmp / "def"
        self.defn.mkdir()
        self.stack = self.tmp / "stack"
        self.stack.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cfg(self, kind, decl):
        (self.defn / "cli.json").write_text(json.dumps({"kind": kind, "flags": ["--tools", ""]}))
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": decl}))
        with patch.dict(os.environ, {"AOS_STACK": str(self.stack)}):
            return cli_session.load_cfg(str(self.defn))

    def test_not_declared_leaves_cli_alone(self):
        (self.stack / "system.txt").write_text("ignored")
        self.assertEqual(cli_session.system_argv(self.cfg("claude", {})), [])
        self.assertEqual(cli_session.system_argv(self.cfg("codex", {})), [])

    def test_claude_definition_then_own_copy(self):
        decl = {"system": "system.txt"}
        self.assertEqual(cli_session.system_argv(self.cfg("claude", decl)), ["--system-prompt-snapshot", "off"])   # no file anywhere
        (self.defn / "system.txt").write_text("from def")
        self.assertEqual(cli_session.system_argv(self.cfg("claude", decl)),
                         ["--system-prompt-snapshot", "off", "--append-system-prompt-file", str(self.defn / "system.txt")])
        (self.stack / "system.txt").write_text("mine")
        self.assertEqual(cli_session.system_argv(self.cfg("claude", decl))[-1], str(self.stack / "system.txt"))
        (self.stack / "system.txt").write_text("")                      # empty own copy = nothing appended (not the definition's)
        self.assertEqual(cli_session.system_argv(self.cfg("claude", decl)), ["--system-prompt-snapshot", "off"])

    def test_codex_developer_instructions(self):
        decl = {"system": "system.txt"}
        self.assertEqual(cli_session.system_argv(self.cfg("codex", decl)), [])
        (self.stack / "system.txt").write_text('Say "hi" ~\nline 2')
        argv = cli_session.system_argv(self.cfg("codex", decl))
        self.assertEqual(argv[0], "-c")
        key, _, value = argv[1].partition("=")
        self.assertEqual((key, json.loads(value)), ("developer_instructions", 'Say "hi" ~\nline 2'))


if __name__ == "__main__":
    unittest.main()
