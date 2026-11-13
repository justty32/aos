"""驗人開的畫面拿到跟 loop 那邊一致的 AOS_CLOCK、AOS_KERNEL、AOS_LLM_KERNEL（11-13 ops-agent-six-suggestions 第 6 點的 bug）：loop 那邊把自己的 MCP_ENV 記進小格 env.json（note_env），開畫面時照它蓋（screen_env、cli_screen.start）；沒記過＝照舊、提醒一行。"""
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
from agent import cli_ask, cli_cell, cli_mcp, cli_screen  # noqa: E402

LOOP = {"AOS_HOME": "/tree/home", "AOS_DAEMON": "/tree/.stack", "AOS_CLOCK": "/tree/.stack/clock", "AOS_LLM_KERNEL": "/tree/llm"}
SHELL = {"AOS_HOME": "/tree/home", "AOS_DAEMON": "/shell/daemon", "AOS_KERNEL": "/shell/kernel", "AOS_STACK": "/s", "AOS_WS": "/w",
         "PATH": os.environ.get("PATH", ""), "HOME": "/home/x", "OTHER": "kept"}


class ScreenEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))
        self.cell = cli_cell.Cell(str(self.d / "cell"))

    def note(self, env=LOOP):
        with patch.dict(os.environ, env, clear=True):
            cli_mcp.note_env(self.cell)

    def test_note_env_keeps_only_the_listed_names_and_rewrites_only_on_change(self):
        self.note(dict(LOOP, AOS_STACK="/x", AOS_CD="/y", PATH="/bin", AOS_CLOCK_INTERVAL=""))
        path = self.cell.file(cli_mcp.ENV_FILE)
        self.assertEqual(json.loads(Path(path).read_text()), LOOP)
        first = os.stat(path).st_ino
        self.note()
        self.assertEqual(os.stat(path).st_ino, first)                       # 一樣＝不重寫
        self.note(dict(LOOP, AOS_CLOCK="/other/clock"))
        self.assertNotEqual(os.stat(path).st_ino, first)
        self.assertEqual(cli_mcp.noted_env(self.cell)["AOS_CLOCK"], "/other/clock")

    def test_screen_env_follows_the_loop_not_the_shell(self):
        self.note()
        with patch.dict(os.environ, SHELL, clear=True):
            env = cli_mcp.screen_env({"kind": "claude"}, self.cell)
            self.assertEqual(dict(os.environ), SHELL)                       # 自己的環境不動
        for k, v in LOOP.items():
            self.assertEqual(env[k], v)
        self.assertNotIn("AOS_KERNEL", env)                                 # loop 那邊沒有的：拿掉
        self.assertEqual((env["AOS_STACK"], env["AOS_WS"], env["OTHER"], env["HOME"]), ("/s", "/w", "kept", "/home/x"))
        self.assertNotIn("AOS_CLI_DEF", env)

    def test_no_record_yet_keeps_the_shell_and_warns_once(self):
        err = io.StringIO()
        with patch.dict(os.environ, SHELL, clear=True), contextlib.redirect_stderr(err):
            env = cli_mcp.screen_env({"kind": "claude"}, self.cell)
        self.assertEqual(env, SHELL)
        self.assertEqual(err.getvalue().count("warning: no env.json in the cell yet"), 1)
        (self.d / "cell" / cli_mcp.ENV_FILE).write_text("not json")
        with patch.dict(os.environ, SHELL, clear=True), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli_mcp.screen_env({"kind": "claude"}, self.cell), SHELL)

    def test_start_runs_tmux_with_the_loop_env_and_puts_the_shell_back(self):
        self.note()
        seen = {}

        def tmux(cell, *args, **kw):
            if "new-session" in args:
                seen["env"], seen["argv"] = dict(os.environ), args
            raise FileNotFoundError("tmux")

        def die(code, reason):
            raise RuntimeError(code)
        with patch.dict(os.environ, SHELL, clear=True), patch.object(cli_cell.Cell, "alive", return_value=False), \
                patch.object(cli_cell.Cell, "tmux", tmux), patch.object(cli_screen.cli_base, "die", die):
            with self.assertRaises(RuntimeError):
                cli_screen.start({"kind": "claude", "flags": []}, self.cell, str(self.d), "")
            self.assertEqual(dict(os.environ), SHELL)
        self.assertEqual(seen["env"]["AOS_CLOCK"], "/tree/.stack/clock")
        self.assertEqual(seen["env"]["AOS_DAEMON"], "/tree/.stack")
        self.assertEqual(seen["env"]["AOS_LLM_KERNEL"], "/tree/llm")
        self.assertNotIn("AOS_KERNEL", seen["env"])
        self.assertEqual(seen["env"]["OTHER"], "kept")

    def test_ask_records_the_env_of_the_asking_side(self):
        with patch.dict(os.environ, LOOP, clear=True), patch.object(cli_cell.Cell, "alive", return_value=False), \
                patch.object(cli_ask, "print_claude", return_value="ok"), patch.object(cli_ask, "link_transcript"):
            cli_ask.ask({"kind": "claude"}, self.cell, str(self.d), str(self.d), str(self.d), "hi")
        self.assertEqual(cli_mcp.noted_env(self.cell), LOOP)


if __name__ == "__main__":
    unittest.main()
