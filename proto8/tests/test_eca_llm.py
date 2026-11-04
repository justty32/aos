"""test_eca_llm - eca 的 llm 子介面（11-04 aos-agent 步 1；thinking 2026-11/04/aos-agent 03/02 介面 aos-agent/llm）：
demo/eca-claude/llm/（_entry → bin/aos-eca-llm ..）經 aos-exec 叫：def 對象讀寫 cli.json 的 --model、stack 對象讀寫 $AOS_STACK/llm.json；
cli_session 每題讀 llm.json 換 --model、讀 $AOS_STACK/tools.json 當登記檔（下一題生效）。假 claude（test_cli_tools），不花額度。"""
import json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, EXEC, tool, path_with  # noqa: E402
from test_cli_tools import FAKE_CLAUDE, SYS_PATH  # noqa: E402
DEMO = ROOT / "demo" / "eca-claude"
TURN = ROOT / "bin" / "aos-eca-turn"
POST = tool("aos-post")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CD", "AOS_CF", "AOS_CO", "AOS_DAEMON", "TMUX",
         "CLAUDE_CONFIG_DIR", "CODEX_HOME", "FAKE_TRANSCRIPTS")


def copy_demo(dst):
    """demo/eca-claude 複製一份（tools.json 的相對路徑改絕對；等回答改 15 秒）。"""
    shutil.copytree(DEMO, dst)
    cfg = json.loads((dst / "cli.json").read_text())
    (dst / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
    (dst / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": str(ROOT / "lib" / "base" / "clock")}}}))
    return dst


class EcaLlm(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eca-llm-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.bin / "claude").write_text(FAKE_CLAUDE)
        (self.bin / "claude").chmod(0o755)
        self.log = self.tmp / "cli.log"
        self.eca = copy_demo(self.tmp / "eca")
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.stack = self.tmp / "stack"
        self.stack.mkdir()

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH=path_with(str(self.bin) + os.pathsep + SYS_PATH), FAKE_LOG=str(self.log), FAKE_TRANSCRIPTS="1",
                 CLAUDE_CONFIG_DIR=str(self.tmp / "claude-home"))
        e.update(extra or {})
        return e

    def llm(self, *args):
        return subprocess.run([EXEC, "--ws", str(self.ws), "--stack", str(self.stack), str(self.eca / "llm")] + list(args),
                              capture_output=True, text=True, env=self.env(), timeout=30, stdin=subprocess.DEVNULL)

    def turn(self, text):
        """寄一封（aos-post）再跑一次 aos-eca-turn；回這次 claude 的 argv。"""
        subprocess.run([POST, "init", str(self.stack / "queue")], check=True, capture_output=True, env=self.env())
        subprocess.run([POST, "send", "--ordered", str(self.stack / "queue")], input=json.dumps({"role": "user", "content": text}),
                       check=True, capture_output=True, text=True, env=self.env())
        r = subprocess.run([str(TURN), str(self.eca)], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
                           env=self.env({"AOS_WS": str(self.ws), "AOS_STACK": str(self.stack) + "/"}))
        self.assertEqual(r.returncode, 0, r.stderr)
        return [json.loads(l) for l in self.log.read_text().splitlines()][-1]["argv"]

    def test_def_show_set(self):
        """def show 印 kind=claude、model=sonnet；def set model=haiku 改到 cli.json（其他鍵、排版照舊）；set kind=＝KeyUnknown。"""
        r = self.llm("def", "show")
        self.assertEqual((r.returncode, r.stdout), (0, "kind=claude\nmodel=sonnet\n"), r.stderr)
        before = (self.eca / "cli.json").read_text()
        r = self.llm("def", "set", "model=haiku")
        self.assertEqual((r.returncode, r.stdout), (0, "kind=claude\nmodel=haiku\n"), r.stderr)
        self.assertEqual((self.eca / "cli.json").read_text(), before.replace('"sonnet"', '"haiku"'))
        r = self.llm("def", "set", "kind=codex")
        self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-eca-llm:", "KeyUnknown"]), r.stderr)
        self.assertEqual(self.llm("def", "reset").returncode, 1)          # reset 只有 stack
        self.assertFalse((self.stack / "llm.json").exists())

    def test_stack_copy(self):
        """stack set 寫 llm.json（定義不動）、stack show 印副本的值、stderr「副本：model」；下一題假 CLI 收到 --model 新值；reset 刪檔、回到定義的。"""
        before = (self.eca / "cli.json").read_text()
        r = self.llm("stack", "set", "model=haiku")
        self.assertEqual((r.returncode, r.stdout), (0, "kind=claude\nmodel=haiku\n"), r.stderr)
        self.assertIn("副本：model", r.stderr)
        self.assertEqual(json.loads((self.stack / "llm.json").read_text()), {"model": "haiku"})
        self.assertEqual((self.eca / "cli.json").read_text(), before)
        argv = self.turn("你好")
        self.assertEqual(argv[argv.index("--model") + 1], "haiku")
        self.assertEqual(argv.count("--model"), 1)
        r = self.llm("stack", "reset")
        self.assertEqual((r.returncode, r.stdout), (0, "kind=claude\nmodel=sonnet\n"), r.stderr)
        self.assertFalse((self.stack / "llm.json").exists())
        argv = self.turn("再一句")
        self.assertEqual(argv[argv.index("--model") + 1], "sonnet")

    def test_stack_tools_copy(self):
        """stack 有 tools.json＝cli_session 用它當登記檔（mcp.json 的最後一個 arg）；沒有＝定義的。"""
        argv = self.turn("幾點")
        mcp = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text())
        self.assertEqual(mcp["mcpServers"]["aos"]["args"][-1], str(self.eca / "tools.json"))
        (self.stack / "tools.json").write_text((self.eca / "tools.json").read_text())
        argv = self.turn("再幾點")
        mcp = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text())
        self.assertEqual(mcp["mcpServers"]["aos"]["args"][-1], str(self.stack / "tools.json"))

    def test_bad(self):
        """動作寫錯＝ArgumentsBad；鍵=值少等號＝ArgumentsBad；stack 對象沒設 AOS_STACK（直接叫 aos-eca-llm）＝StackMissing；llm.json 壞＝CfgBad。"""
        self.assertEqual(self.llm("def", "zzz").returncode, 1)
        r = self.llm("stack", "set", "model")
        self.assertEqual(r.stderr.split()[:2], ["aos-eca-llm:", "ArgumentsBad"])
        r = subprocess.run([str(ROOT / "bin" / "aos-eca-llm"), str(self.eca), "stack", "show"], capture_output=True, text=True,
                           env=self.env(), timeout=30)
        self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-eca-llm:", "StackMissing"]))
        (self.stack / "llm.json").write_text("{壞")
        r = self.llm("stack", "show")
        self.assertEqual(r.stderr.split()[:2], ["aos-eca-llm:", "CfgBad"])


if __name__ == "__main__":
    unittest.main()
