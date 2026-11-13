"""驗 cli.json 的 flags／print_flags 不准再寫 aos 自己會加的旗標（11-13 eca_main 第 6 項：codex 的 --skip-git-repo-check 寫第二次＝codex 退 2、信被丟）：讀設定時就 CfgBad。"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LIB))
from agent import cli_cfg  # noqa: E402


class ReservedFlags(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}

    def load(self, **cfg):
        (self.d / "cli.json").write_text(json.dumps(cfg))
        with patch.dict(os.environ, self.env, clear=True):
            return cli_cfg.load_cfg(str(self.d))

    def fails(self, **cfg):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.load(**cfg)
        self.assertEqual(cm.exception.code, 1)
        line = err.getvalue().strip().splitlines()[-1]
        self.assertIn("error: CfgBad %s: " % (self.d / "cli.json"), line)
        return line

    def test_codex_print_flags_skip_git_repo_check_is_cfgbad(self):
        line = self.fails(kind="codex", print_flags=["--skip-git-repo-check"])
        self.assertTrue(line.endswith("print_flags has --skip-git-repo-check, which aos adds itself; remove it"), line)

    def test_codex_flags_json_is_cfgbad(self):
        self.assertIn("flags has --json, which aos adds itself", self.fails(kind="codex", flags=["-c", "a=1", "--json"]))
        for flag in ("-o", "--output-last-message", "--output-last-message=/tmp/x"):
            with self.subTest(flag=flag):
                self.assertIn("print_flags has %s, which aos adds itself" % flag.split("=")[0],
                              self.fails(kind="codex", print_flags=[flag, "x"]))

    def test_claude_flags_resume_is_cfgbad(self):
        self.assertIn("flags has --resume, which aos adds itself", self.fails(kind="claude", flags=["--resume", "abc"]))
        for flag in ("-p", "--print", "--output-format", "--output-format=json", "--session-id", "-r", "--continue", "-c"):
            with self.subTest(flag=flag):
                self.fails(kind="claude", print_flags=[flag])

    def test_several_are_all_named(self):
        self.assertIn("print_flags has --json, --skip-git-repo-check, which aos adds itself",
                      self.fails(kind="codex", print_flags=["--skip-git-repo-check", "--json"]))

    def test_other_flags_pass(self):
        codex = self.load(kind="codex", flags=["-c", 'sandbox_mode="workspace-write"', "-c", 'approval_policy="never"', "--model", "gpt-x"],
                          print_flags=["--color", "never"])
        self.assertEqual(codex["print_flags"], ["--color", "never"])          # -c is codex's config override, repeatable
        claude = self.load(kind="claude", flags=["--tools", "default", "--permission-mode", "dontAsk", "--allowedTools", "Read",
                                                 "--strict-mcp-config", "--model", "sonnet", "--verbose"],
                           print_flags=["--max-budget-usd", "0.5"])
        self.assertEqual(claude["print_flags"], ["--max-budget-usd", "0.5"])

    def test_shipped_cli_json_files_pass(self):
        proto = LIB.parent
        for path in sorted(list(proto.glob("templates/*/cli.json")) + list(proto.glob("lib/agent/*/cli.json"))):
            with self.subTest(path=str(path)):
                cfg = json.loads(path.read_text())
                for k in ("flags", "print_flags"):
                    self.assertEqual(cli_cfg.reserved_flags(cfg["kind"], cfg.get(k, [])), [])


if __name__ == "__main__":
    unittest.main()
