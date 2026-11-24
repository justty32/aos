"""驗 cli.json 的 claude_mcp（11-24）：claude 自己設定裡的 MCP server（user、project 核准過的、local＝這個 cwd 的）抄進小格的 mcp.json、
放行 mcp__<名>；--strict-mcp-config 照留，工作區沒核准的 .mcp.json 進不來；換帳號（CLAUDE_CONFIG_DIR）、換 cwd 各自照那份設定。"""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from aos.agentlib import cli_cell, cli_cfg, cli_mcp  # noqa: E402

USER = {"type": "stdio", "command": "user-server", "args": []}
LOCAL = {"type": "http", "url": "https://team.example/mcp", "headers": {"Authorization": "Bearer t0ken"}}


class ClaudeMcp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.d, self.ws, self.conf = self.root / "def", self.root / "ws", self.root / "conf"
        for p in (self.d, self.ws, self.conf):
            p.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env["CLAUDE_CONFIG_DIR"] = str(self.conf)
        self.write_conf({"mcpServers": {"usr": USER},
                         "projects": {str(self.ws): {"mcpServers": {"team": LOCAL}, "enabledMcpjsonServers": ["ok"]},
                                      str(self.root): {"mcpServers": {"parent": USER}}}})
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {"ok": USER, "unapproved": USER}}))

    def write_conf(self, doc):
        (self.conf / ".claude.json").write_text(json.dumps(doc))

    def load(self, **cfg):
        (self.d / "cli.json").write_text(json.dumps(dict({"kind": "claude"}, **cfg)))
        with patch.dict(os.environ, self.env, clear=True):
            return cli_cfg.load_cfg(str(self.d))

    def argv(self, cfg, ws=None):
        cell = cli_cell.Cell(str(self.root / "cell"))
        os.makedirs(cell.path, exist_ok=True)
        err = io.StringIO()
        with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stderr(err):
            argv = cli_mcp.mcp_argv(cfg, cell, str(ws or self.ws), str(self.root / "stack"))
        mcp = json.loads(Path(cell.file("mcp.json")).read_text()) if argv else None
        return argv, mcp, err.getvalue(), cell

    def test_all_scopes(self):
        argv, mcp, err, cell = self.argv(self.load(claude_mcp=["user", "project", "local"]))
        self.assertEqual(err, "")
        self.assertEqual(mcp["mcpServers"], {"usr": USER, "ok": USER, "team": LOCAL})
        self.assertEqual(argv[:2], ["--mcp-config", cell.file("mcp.json")])
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "mcp__usr,mcp__ok,mcp__team")
        self.assertEqual(stat.S_IMODE(os.stat(cell.file("mcp.json")).st_mode), 0o600)   # may hold a token

    def test_scopes_cwd_and_account(self):
        _, mcp, _, _ = self.argv(self.load(claude_mcp=["local"]))
        self.assertEqual(list(mcp["mcpServers"]), ["team"])
        sub = self.ws / "sub"
        sub.mkdir()
        argv, _, _, _ = self.argv(self.load(claude_mcp=["local"]), ws=sub)             # local = the exact cwd only
        self.assertEqual(argv, [])
        self.env["CLAUDE_CONFIG_DIR"] = str(self.root / "other-account")                 # no .claude.json there
        self.assertEqual(self.argv(self.load(claude_mcp=["user", "local"]))[0], [])
        del self.env["CLAUDE_CONFIG_DIR"]
        with patch.dict(os.environ, {"HOME": str(self.conf)}):
            self.env["HOME"] = str(self.conf)                                              # unset = ~/.claude.json
            _, mcp, _, _ = self.argv(self.load(claude_mcp=["user"]))
        self.assertEqual(list(mcp["mcpServers"]), ["usr"])

    def test_absent_key_and_project_approval(self):
        self.assertEqual(self.argv(self.load())[0], [])                                  # no key = nothing taken (as before)
        self.write_conf({"projects": {str(self.ws): {"enableAllProjectMcpServers": True,
                                                     "disabledMcpjsonServers": ["unapproved"]}}})
        _, mcp, _, _ = self.argv(self.load(claude_mcp=["project"]))
        self.assertEqual(list(mcp["mcpServers"]), ["ok"])

    def test_names_taken_and_bad_files(self):
        self.write_conf({"mcpServers": {"aos": USER, "aos_sub": USER, "fine": USER, "bad": "x"}})
        _, mcp, err, _ = self.argv(self.load(claude_mcp=["user"]))
        self.assertEqual(list(mcp["mcpServers"]), ["fine"])
        self.assertIn("MCP server aos skipped", err)
        self.assertIn("'bad'", err)
        (self.conf / ".claude.json").write_text("{broken")
        argv, _, err, _ = self.argv(self.load(claude_mcp=["user"]))
        self.assertEqual(argv, [])
        self.assertIn("claude_mcp: cannot read", err)

    def test_bad_key_is_cfgbad(self):
        for bad, kind in (("user", "claude"), (["everything"], "claude"), (["user"], "codex")):
            with self.subTest(bad=bad, kind=kind):
                (self.d / "cli.json").write_text(json.dumps({"kind": kind, "claude_mcp": bad}))
                err = io.StringIO()
                with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stderr(err), \
                        self.assertRaises(SystemExit):
                    cli_cfg.load_cfg(str(self.d))
                self.assertIn("CfgBad", err.getvalue())
                self.assertIn("claude_mcp", err.getvalue())

    def test_shipped_claude_templates_keep_strict_and_take_all_scopes(self):
        proto = LIB.parent
        for rel in ("templates/eca-claude/cli.json", "templates/eca-claude-alt/cli.json", "templates/start-eca/agents/ann/cli.json"):
            with self.subTest(path=rel):
                cfg = json.loads((proto / rel).read_text())
                self.assertIn("--strict-mcp-config", cfg["flags"])
                self.assertEqual(cfg.get("claude_mcp"), ["user", "project", "local"])


if __name__ == "__main__":
    unittest.main()
