"""驗 cli.json 的 tools_sub（11-12 eca-task-subagent）：只有 claude 身認、--agents 蓋掉 general-purpose 並內嵌 aos_sub、--allowedTools 多 mcp__aos_sub、guard hook 擋子 agent 叫主 agent 那台；範本 eca-claude 開 Agent、Skill 且子 agent 那台只有唯讀八支。"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LIB))
from agent import cli_session  # noqa: E402

TEMPLATE = LIB.parent / "templates" / "eca-claude"
SUB_TOOLS = ["index_view", "json_get", "json_ls", "json_multi_get", "json_search", "math", "peek_clock", "peek_now_time"]


class ToolsSub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        for name in ("tools.json", "tools_sub.json"):
            (self.d / name).write_text('{"tools": {}}\n')
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}

    def write(self, **cfg):
        (self.d / "cli.json").write_text(json.dumps(dict({"kind": "claude"}, **cfg)))

    def load(self):
        with patch.dict(os.environ, self.env, clear=True):
            return cli_session.load_cfg(str(self.d))

    def fails(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.load()
        self.assertEqual(cm.exception.code, 1)
        return err.getvalue().strip().splitlines()[-1]

    def argv(self, cfg):
        cell = cli_session.Cell(str(self.d / "cell"))
        with patch.object(cli_session.shutil, "which", lambda n: "/bin/" + n):
            return cli_session.mcp_argv(cfg, cell, "/w", "/st"), cell

    def test_absent_means_nothing_added(self):
        self.write()
        cfg = self.load()
        self.assertIsNone(cfg["sub_registry"])
        argv, cell = self.argv(cfg)
        self.assertEqual(argv, ["--mcp-config", cell.file("mcp.json"), "--allowedTools", "mcp__aos"])
        self.assertEqual(cli_session.guard_hooks(cfg), {})

    def test_claude_gets_agents_and_allow(self):
        self.write(tools_sub="tools_sub.json", tools_flags=["--enable-logs"])
        cfg = self.load()
        self.assertEqual(cfg["sub_registry"], str(self.d / "tools_sub.json"))
        argv, cell = self.argv(cfg)
        self.assertEqual(argv[:4], ["--mcp-config", cell.file("mcp.json"), "--allowedTools", "mcp__aos,mcp__aos_sub"])
        self.assertEqual(argv[4], "--agents")
        agents = json.loads(argv[5])
        self.assertEqual(list(agents), ["general-purpose"])
        gp = agents["general-purpose"]
        self.assertEqual(gp["disallowedTools"], ["mcp__aos"])
        self.assertTrue(gp["description"] and gp["prompt"])
        self.assertNotIn("tools", gp)                       # 內建工具照繼承
        self.assertEqual(gp["mcpServers"], [{"aos_sub": {"command": "aos-mcp", "args": [
            "--ws", "/w", "--stack", "/st", "--enable-logs", str(self.d / "tools_sub.json")]}}])
        self.assertEqual(list(json.loads(Path(cell.file("mcp.json")).read_text())["mcpServers"]), ["aos"])   # 主對話那份沒有 aos_sub

    def test_hooks_def_goes_to_sub_server(self):
        self.write(tools_sub="tools_sub.json")
        cfg = dict(self.load(), hooks_def="/defs/x")
        with patch.object(cli_session.shutil, "which", lambda n: "/bin/" + n):
            agents = cli_session.sub_agents(cfg, "/w", "/st")
        self.assertEqual(agents["general-purpose"]["mcpServers"][0]["aos_sub"]["args"][4:6], ["--hooks", "/defs/x"])

    def test_codex_refused(self):
        self.write(kind="codex", tools_sub="tools_sub.json")
        self.assertIn("CfgBad", self.fails())

    def test_own_agents_flag_refused(self):
        self.write(tools_sub="tools_sub.json", flags=["--agents", "{}"])
        line = self.fails()
        self.assertIn("CfgBad", line)
        self.assertIn("--agents", line)

    def test_missing_file(self):
        self.write(tools_sub="nope.json")
        self.assertIn("ToolsMissing", self.fails())

    def test_bad_value(self):
        self.write(tools_sub=3)
        self.assertIn("CfgBad", self.fails())

    def test_guard_hook_table(self):
        self.write(tools_sub="tools_sub.json")
        hooks = cli_session.guard_hooks(self.load())
        self.assertEqual(list(hooks), ["PreToolUse"])
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "mcp__aos__.*")
        self.assertTrue(hooks["PreToolUse"][0]["hooks"][0]["command"].endswith(" guard"))

    def guard(self, payload):
        r = subprocess.run([sys.executable, str(LIB / "agent" / "cli_session.py"), "guard"], input=payload,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_guard_main_agent_passes(self):
        self.assertEqual(self.guard(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "mcp__aos__math"})), "")

    def test_guard_subagent_denied(self):
        out = json.loads(self.guard(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "mcp__aos__math",
                                                "agent_id": "a1", "agent_type": "Explore"})))
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("mcp__aos_sub__", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_guard_unreadable_input_denied(self):
        self.assertEqual(json.loads(self.guard("not json"))["hookSpecificOutput"]["permissionDecision"], "deny")


class Template(unittest.TestCase):
    def test_cli_json_opens_agent_and_skill(self):
        cfg = json.loads((TEMPLATE / "cli.json").read_text())
        tools = cfg["flags"][cfg["flags"].index("--tools") + 1].split(",")
        self.assertIn("Agent", tools)
        self.assertIn("Skill", tools)
        self.assertEqual(cfg["tools_sub"], "tools_sub.json")
        self.assertFalse(any("dangerously" in f or f == "bypassPermissions" for f in cfg["flags"]))

    @unittest.skipUnless(shutil.which("aos-tools"), "aos-tools not on PATH")
    def test_sub_registry_is_the_read_only_eight(self):
        env = dict(os.environ, AOS_HOME=str(LIB.parent))
        r = subprocess.run(["aos-tools", "--file", str(TEMPLATE / "tools_sub.json"), "ls", "--json"],
                           capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = json.loads(r.stdout)
        self.assertEqual(sorted(t["name"] for t in rows), SUB_TOOLS)
        self.assertEqual([t["name"] for t in rows if (t.get("metainfo") or {}).get("side_effect") is not False], [])


if __name__ == "__main__":
    unittest.main()
