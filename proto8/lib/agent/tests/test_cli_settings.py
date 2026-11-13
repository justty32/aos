"""驗 cli.json 的 settings（11-13 ops-agent-six-suggestions 第 1 題乙：定義自帶 Claude Code 設定）與 flags 裡的 --settings（＝CfgBad，以前被 aos 自己那個靜默蓋掉）：aos 把定義的設定併進它自己加的那一個 --settings，命令列上只有一個。"""
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
from agent import cli_cell, cli_cfg, cli_mcp, cli_print, cli_screen  # noqa: E402

GATE = {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 \"$AOS_CLI_DEF/gate.py\""}]}
GUARD = {"PreToolUse": [{"matcher": "mcp__aos__.*", "hooks": [{"type": "command", "command": "guard"}]}]}


class Settings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}

    def load(self, **cfg):
        (self.d / "cli.json").write_text(json.dumps(dict({"kind": "claude"}, **cfg)))
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

    # ---- B2: flags 裡的 --settings
    def test_settings_flag_in_flags_is_cfgbad_and_points_to_the_key(self):
        for key in ("flags", "print_flags"):
            for flag in (["--settings", "{}"], ["--settings={}"]):
                with self.subTest(key=key, flag=flag):
                    line = self.fails(**{key: flag})
                    self.assertIn("%s has --settings, which aos adds itself; remove it" % key, line)
                    self.assertIn("settings key of cli.json", line)

    # ---- B3: settings 鍵
    def test_absent_means_exactly_what_it_was(self):
        cfg = self.load()
        self.assertIsNone(cfg["cli_settings"])
        self.assertEqual(cli_mcp.settings_argv(cfg, {}), [])
        mine = {"hooks": dict(GUARD), "crossSessionInbound": "accept"}
        self.assertEqual(cli_mcp.settings_argv(cfg, mine), ["--settings", json.dumps(mine)])
        self.assertEqual(cli_mcp.settings_env(cfg), {})

    def test_object_is_merged_under_what_aos_adds(self):
        cfg = self.load(settings={"hooks": {"PreToolUse": [GATE], "PostToolUse": [GATE]}, "permissions": {"deny": ["Bash(rm:*)"]},
                                  "crossSessionInbound": "refuse"})
        mine = {"hooks": dict(GUARD, Stop=[{"hooks": []}]), "crossSessionInbound": "accept"}
        flag, value = cli_mcp.settings_argv(cfg, mine)
        got = json.loads(value)
        self.assertEqual(flag, "--settings")
        self.assertEqual(got["hooks"]["PreToolUse"], [GATE] + GUARD["PreToolUse"])     # 兩邊都在：定義的在前、aos 的在後
        self.assertEqual(got["hooks"]["PostToolUse"], [GATE])
        self.assertEqual(got["hooks"]["Stop"], [{"hooks": []}])
        self.assertEqual(got["permissions"], {"deny": ["Bash(rm:*)"]})
        self.assertEqual(got["crossSessionInbound"], "refuse")                          # 定義寫了的頂層鍵照定義
        self.assertEqual(cli_mcp.settings_argv(cfg, {})[1], json.dumps(cfg["cli_settings"]))   # aos 沒東西要加也照帶
        self.assertEqual(cli_mcp.settings_env(cfg), {"AOS_CLI_DEF": str(self.d)})
        self.assertEqual(mine["hooks"]["PreToolUse"], GUARD["PreToolUse"])              # 不改到傳進來的

    def test_file_is_read_from_the_definition_folder_each_time(self):
        (self.d / "claude_settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [GATE]}}))
        self.assertEqual(self.load(settings="claude_settings.json")["cli_settings"], {"hooks": {"PreToolUse": [GATE]}})
        (self.d / "claude_settings.json").write_text(json.dumps({"permissions": {}}))
        self.assertEqual(self.load(settings="claude_settings.json")["cli_settings"], {"permissions": {}})

    def test_bad_shapes_are_cfgbad(self):
        (self.d / "list.json").write_text("[]")
        (self.d / "broken.json").write_text("{")
        for value, part in (([], "settings must be an object"), (3, "settings must be an object"), ("", "settings must be an object"),
                            ("nope.json", "cannot be read as JSON"), ("broken.json", "cannot be read as JSON"),
                            ("list.json", "settings must be an object"), ({"hooks": []}, "hooks in settings must be an object"),
                            ({"hooks": {"PreToolUse": {}}}, "hooks in settings must be an object")):
            with self.subTest(value=value):
                self.assertIn(part, self.fails(settings=value))
        self.assertIn("settings is only for kind claude", self.fails(kind="codex", settings={}))

    def test_print_path_passes_one_settings_flag_and_the_definition_folder(self):
        cfg = self.load(settings={"hooks": {"PreToolUse": [GATE]}})
        seen = {}

        def run(argv, prompt, ws, timeout_ms, live_path, handed=None, env=None):
            seen["argv"], seen["env"] = argv, env
            return 0, [json.dumps({"type": "result", "result": "ok", "session_id": "s"}) + "\n"]
        cell = cli_cell.Cell(str(self.d / "cell"))
        with patch.object(cli_print, "run_claude_stream", run), patch.object(cli_print, "mcp_argv", return_value=[]), \
                patch.object(cli_print, "mark_session"):
            self.assertEqual(cli_print.print_claude(cfg, cell, str(self.d), str(self.d), "hi", None, ""), "ok")
        self.assertEqual(seen["argv"].count("--settings"), 1)
        self.assertEqual(json.loads(seen["argv"][seen["argv"].index("--settings") + 1]), {"hooks": {"PreToolUse": [GATE]}})
        self.assertEqual(seen["env"], {"AOS_CLI_DEF": str(self.d)})
        cfg = self.load()                                                               # 沒寫 settings：照舊沒有 --settings、不加環境
        with patch.object(cli_print, "run_claude_stream", run), patch.object(cli_print, "mcp_argv", return_value=[]), \
                patch.object(cli_print, "mark_session"):
            cli_print.print_claude(cfg, cell, str(self.d), str(self.d), "hi", None, "")
        self.assertNotIn("--settings", seen["argv"])
        self.assertIsNone(seen["env"])

    def test_screen_path_merges_into_its_one_settings_flag(self):
        cfg = self.load(settings={"hooks": {"PreToolUse": [GATE], "Stop": [GATE]}})
        cell = cli_cell.Cell(str(self.d / "cell"))
        seen = {}

        def tmux(cell, *args, **kw):
            if "new-session" in args:
                seen["argv"], seen["def"] = list(args), os.environ.get("AOS_CLI_DEF")
            raise FileNotFoundError("tmux")

        def die(code, reason):
            raise RuntimeError(code)
        with patch.dict(os.environ, self.env, clear=True), patch.object(cli_cell.Cell, "alive", return_value=False), \
                patch.object(cli_cell.Cell, "tmux", tmux), patch.object(cli_screen.cli_base, "die", die), \
                patch.object(cli_screen, "mcp_argv", return_value=[]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(RuntimeError):
                cli_screen.start(cfg, cell, str(self.d), "")
            self.assertNotIn("AOS_CLI_DEF", os.environ)
        self.assertEqual(seen["argv"].count("--settings"), 1)
        got = json.loads(seen["argv"][seen["argv"].index("--settings") + 1])
        self.assertEqual(got["hooks"]["PreToolUse"], [GATE])
        self.assertEqual(got["hooks"]["Stop"][0], GATE)                                 # 定義的 Stop 在前
        self.assertIn("cli_session.py", got["hooks"]["Stop"][1]["hooks"][0]["command"])   # aos 收回答的那個還在
        self.assertEqual(sorted(got["hooks"]), ["PreToolUse", "SessionStart", "Stop", "UserPromptSubmit"])
        self.assertEqual(got["crossSessionInbound"], "accept")
        self.assertEqual(seen["def"], str(self.d))

    def test_shipped_templates_have_no_settings(self):
        proto = LIB.parent
        for path in sorted(list(proto.glob("templates/*/cli.json")) + list(proto.glob("lib/agent/*/cli.json"))):
            with self.subTest(path=str(path)):
                self.assertNotIn("settings", json.loads(path.read_text()))             # 範本預設全面開放（使用者 11-13）


if __name__ == "__main__":
    unittest.main()
