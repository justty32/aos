"""test_eca_screen - eca 的 screen 子介面（11-04 aos-agent 步 1；thinking 2026-11/04/aos-agent 03/02 介面 aos-agent/screen）：
demo/eca-claude/screen/（_entry → bin/aos-eca-screen ..）經 `aos-exec --ws W --stack S <eca>/screen open -d|close|watch` 叫；
open／close／watch 的身體 11-04 從 aos-eca 搬來（原 test_eca_cmd 的 open／close 案搬這裡、改直接叫入口，不經 daemon）。
假 claude（test_cli_tools），不花額度；open -d 要 tmux（沒有就 skip）。"""
import json, os, shutil, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, EXEC, tool, path_with  # noqa: E402
from test_cli_tools import FAKE_CLAUDE, SYS_PATH, HAS_TMUX  # noqa: E402
from test_eca_llm import copy_demo, CLEAR  # noqa: E402
TURN = ROOT / "bin" / "aos-eca-turn"
POST = tool("aos-post")


class EcaScreen(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eca-screen-"))
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
        self.sock = self.stack / "claude" / "tty.sock"
        self.addCleanup(lambda: subprocess.run(["tmux", "-S", str(self.sock), "kill-server"], capture_output=True))

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH=path_with(str(self.bin) + os.pathsep + SYS_PATH), FAKE_LOG=str(self.log), FAKE_TRANSCRIPTS="1",
                 CLAUDE_CONFIG_DIR=str(self.tmp / "claude-home"))
        e.update(extra or {})
        return e

    def screen(self, *args, timeout=60):
        return subprocess.run([EXEC, "--ws", str(self.ws), "--stack", str(self.stack), str(self.eca / "screen")] + list(args),
                              capture_output=True, text=True, env=self.env(), timeout=timeout, stdin=subprocess.DEVNULL)

    def turn(self, text):
        subprocess.run([POST, "init", str(self.stack / "queue")], check=True, capture_output=True, env=self.env())
        subprocess.run([POST, "send", "--ordered", str(self.stack / "queue")], input=json.dumps({"role": "user", "content": text}),
                       check=True, capture_output=True, text=True, env=self.env())
        r = subprocess.run([str(TURN), str(self.eca)], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
                           env=self.env({"AOS_WS": str(self.ws), "AOS_STACK": str(self.stack) + "/"}))
        self.assertEqual(r.returncode, 0, r.stderr)
        h = [json.loads(l) for l in (self.stack / "history.jsonl").read_text().splitlines()]
        return h[-1]["content"]

    def code(self, r):
        return (r.returncode, (r.stderr.split() + ["", ""])[1])

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_open_close(self):
        """open -d：開畫面（tty.sock、Ctrl-] 只跳出）；再 open -d＝本來就開著；畫面開著時那一題打進畫面（fake live）；
        close＝收起了、tmux 不在；再 close＝本來就沒畫面；之後那一題照答（--resume）。"""
        r = self.screen("open", "-d")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.sock.exists())
        keys = subprocess.run(["tmux", "-S", str(self.sock), "list-keys", "-T", "root"], capture_output=True, text=True).stdout
        self.assertIn("C-]", keys)
        r = self.screen("open", "-d")
        self.assertEqual((r.returncode, r.stdout.split("：")[0]), (0, "畫面本來就開著"), r.stderr)
        self.assertEqual(self.turn("畫面上的一句"), "fake live: 畫面上的一句")
        r = self.screen("close")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "收起了"), r.stderr)
        self.assertNotEqual(subprocess.run(["tmux", "-S", str(self.sock), "has-session"], capture_output=True).returncode, 0)
        r = self.screen("close")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "本來就沒畫面（已收起）"), r.stderr)
        self.assertIn("又一句", self.turn("又一句"))

    def test_close_busy(self):
        """正在答題（格的 lock 被拿著）時 close＝SessionBad。"""
        import fcntl
        cell = self.stack / "claude"
        cell.mkdir()
        with open(cell / "lock", "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            self.assertEqual(self.code(self.screen("close")), (1, "SessionBad"))

    def test_watch(self):
        """watch 從 live.jsonl 現在的尾巴跟著看，印開始／文字／結束，看到 result 就走（退 0）。"""
        cell = self.stack / "claude"
        cell.mkdir()
        live = cell / "live.jsonl"
        live.write_text(json.dumps({"type": "result", "is_error": False}) + "\n")      # 舊的不印
        p = subprocess.Popen([EXEC, "--ws", str(self.ws), "--stack", str(self.stack), str(self.eca / "screen"), "watch"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env(), stdin=subprocess.DEVNULL)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        time.sleep(1.0)
        with open(live, "a") as f:
            for ev in ({"type": "system", "subtype": "init", "session_id": "abcdefgh12", "model": "haiku"},
                       {"type": "assistant", "message": {"content": [{"type": "text", "text": "幾點了"}]}},
                       {"type": "result", "is_error": False, "total_cost_usd": 0.01}):
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0, err)
        self.assertEqual(out.splitlines(), ["── 開始（對話 abcdefgh，模型 haiku）", "幾點了", "── 結束（完成，0.0100 美元）"])

    def test_bad(self):
        """動作不認得＝ArgumentsBad；不給 AOS_STACK 直接叫＝StackMissing；open 多帶參數＝ArgumentsBad。"""
        self.assertEqual(self.code(self.screen("zzz")), (1, "ArgumentsBad"))
        self.assertEqual(self.code(self.screen("open", "-x")), (1, "ArgumentsBad"))
        r = subprocess.run([str(ROOT / "bin" / "aos-eca-screen"), str(self.eca), "close"], capture_output=True, text=True,
                           env=self.env(), timeout=30)
        self.assertEqual(self.code(r), (1, "StackMissing"))


if __name__ == "__main__":
    unittest.main()
