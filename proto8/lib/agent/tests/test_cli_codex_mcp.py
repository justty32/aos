"""驗 cli_session 起 codex 時給 aos MCP server 的設定（11-11）：明寫帶 AOS_* 環境（只帶清單裡有設的，AOS_WS／AOS_STACK 用這次的值），只對 aos 這個 server 免核准；claude 那邊不變。"""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent import cli_session  # noqa: E402


class CodexMcp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cli-codex-mcp-"))
        (self.tmp / "tools.json").write_text('{"tools": {}}')
        self.cfg = {"kind": "codex", "registry": str(self.tmp / "tools.json")}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def settings(self, env):
        with patch.dict(os.environ, env, clear=True), patch.object(cli_session.shutil, "which", lambda n: "/bin/" + n):
            argv = cli_session.mcp_argv(self.cfg, None, "/w s", "/st")
        self.assertEqual(argv[::2], ["-c"] * (len(argv) // 2))
        return tomllib.loads("\n".join(argv[1::2]))["mcp_servers"]["aos"]   # every -c value parses as TOML

    def test_env_and_approval(self):
        aos = self.settings({"PATH": "/usr/bin", "HOME": "/h", "AOS_HOME": "/p8", "AOS_DAEMON": "/d", "AOS_CLOCK": "",
                             "AOS_STACK": "/other", "AOS_CD": "/def", "AOS_AGENT": "bob", "SECRET": "x"})
        self.assertEqual(aos["command"], "aos-mcp")
        self.assertEqual(aos["args"][:4], ["--ws", "/w s", "--stack", "/st"])
        self.assertEqual(aos["env"], {"AOS_HOME": "/p8", "AOS_DAEMON": "/d", "AOS_WS": "/w s", "AOS_STACK": "/st"})
        self.assertEqual(aos["default_tools_approval_mode"], "approve")

    def test_quotes_survive(self):
        aos = self.settings({"AOS_HOME": 'a "b" \\ c ü'})
        self.assertEqual(aos["env"]["AOS_HOME"], 'a "b" \\ c ü')

    def test_claude_unchanged(self):
        cell = cli_session.Cell(str(self.tmp / "cell"))
        with patch.object(cli_session.shutil, "which", lambda n: "/bin/" + n):
            argv = cli_session.mcp_argv(dict(self.cfg, kind="claude"), cell, "/w", "/st")
        self.assertEqual(argv, ["--mcp-config", cell.file("mcp.json"), "--allowedTools", "mcp__aos"])
        self.assertNotIn("env", json.loads(Path(cell.file("mcp.json")).read_text())["mcpServers"]["aos"])


if __name__ == "__main__":
    unittest.main()
