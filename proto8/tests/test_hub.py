"""test_hub - proto8/extras/cli_hub 的 aos-hub：列出所有 claude 小格、收起閒著的、叫回收起的、看即時紀錄。

用 test_fay 的假 claude，不花額度；要 tmux（沒有就 skip 畫面那幾個）。
設計：proto8/thinking/2026-10-27-claude-switch.md。"""
import json, os, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, path_with  # noqa: E402
from test_fay import FAKE_CLAUDE, SYS_PATH, HAS_TMUX  # noqa: E402
HUB = ROOT / "extras" / "cli_hub" / "bin" / "aos-hub"
TOOL = ROOT / "lib" / "agent" / "claude"
CLEAR = ("AOS_HUB", "AOS_WS", "AOS_ENTRY", "AOS_STACK", "TMUX")


class Hub(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hub-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.bin / "claude").write_text(FAKE_CLAUDE)
        (self.bin / "claude").chmod(0o755)
        self.log = self.tmp / "cli.log"
        self.tool_dir = self.tmp / "tools" / "claude"           # 複製工具，cli.json 等回答改 15 秒
        shutil.copytree(TOOL, self.tool_dir)
        cfg = json.loads((self.tool_dir / "cli.json").read_text())
        (self.tool_dir / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
        os.symlink(ROOT / "lib" / "agent" / "cli_session.py", self.tmp / "tools" / "cli_session.py")
        self.socks = []
        self.addCleanup(self.kill_all)

    def kill_all(self):
        for s in self.socks:
            subprocess.run(["tmux", "-S", str(s), "kill-server"], capture_output=True)

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH=path_with(str(self.bin) + os.pathsep + SYS_PATH), FAKE_LOG=str(self.log),
                 AOS_HUB=str(self.tmp / "hub"))
        e.update(extra or {})
        return e

    def ask(self, ws, prompt):
        """像 agent 那樣叫 claude 工具：小格＝<ws>/.stack/claude/。"""
        ws.mkdir(parents=True, exist_ok=True)
        cell = ws / ".stack" / "claude"
        self.socks.append(cell / "tty.sock")
        r = subprocess.run([str(self.tool_dir / "_entry")], input=json.dumps({"prompt": prompt}), text=True,
                           capture_output=True, env=self.env(dict(AOS_WS=str(ws), AOS_STACK=str(cell) + "/")), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return cell

    def hub(self, *args, cwd=None):
        return subprocess.run([str(HUB), *args], capture_output=True, text=True, env=self.env(), cwd=cwd,
                              stdin=subprocess.DEVNULL, timeout=60)

    def ls(self):
        r = self.hub("ls", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_register_and_list(self):
        a = self.ask(self.tmp / "ws-a", "第一句")
        self.ask(self.tmp / "ws-b", "第二句")
        rows = self.ls()
        self.assertEqual([r["ws"] for r in rows], [str(self.tmp / "ws-a"), str(self.tmp / "ws-b")])
        self.assertEqual({r["state"] for r in rows}, {"收起了"})          # 只有非互動用過：沒畫面、對話留著
        self.assertEqual(rows[0]["session"], (a / "session.txt").read_text().strip())
        self.assertTrue((a / "live.jsonl").exists())                     # 非互動那次的即時紀錄
        shutil.rmtree(self.tmp / "ws-b")                                 # 格不在了：捷徑拿掉
        self.assertEqual(len(self.ls()), 1)

    def test_no_args_lists_cells_here(self):
        self.ask(self.tmp / "ws-a", "一")
        (self.tmp / "else").mkdir()
        r = self.hub(cwd=self.tmp / "else")                              # 這裡沒格：列全部，stdin 空＝不選
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("列全部", r.stderr)
        self.assertIn("ws-a", r.stdout)
        self.ask(self.tmp / "ws-b", "二")
        r = self.hub(cwd=self.tmp)                                       # 底下兩格：只列這兩格選
        self.assertEqual((r.returncode, r.stdout.count("收起了")), (0, 2), r.stderr)
        r = self.hub("bogus")
        self.assertEqual((r.returncode, r.stderr.split()[1]), (1, "ArgumentsBad"))
        r = self.hub("attach", "9")
        self.assertEqual((r.returncode, r.stderr.split()[1]), (1, "CellMissing"))

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_stop_idle_and_recall(self):
        cell = self.ask(self.tmp / "ws-a", "一")
        sid = (cell / "session.txt").read_text().strip()
        r = self.hub("attach", "-d", "1")                                # 開畫面（不接）
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ls()[0]["state"], "畫面閒著")
        r = self.hub("stop", "--idle", "60")                             # 還沒閒那麼久：不收
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        (cell / "busy.txt").write_text("x")                              # 正在跑一輪：指名也不收
        r = self.hub("stop", "1")
        self.assertIn("沒收", r.stdout)
        os.remove(cell / "busy.txt")
        r = self.hub("stop", "--idle", "0")
        self.assertIn("收起", r.stdout)
        self.assertEqual(self.ls()[0]["state"], "收起了")
        self.assertEqual((cell / "session.txt").read_text().strip(), sid)
        r = self.hub("attach", "-d", "1")                                # 叫回：--resume 同一段
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("叫回", r.stdout)
        last = [json.loads(l) for l in self.log.read_text().splitlines()][-1]["argv"]
        self.assertEqual(last[last.index("--resume") + 1], sid)
        self.assertNotIn("-p", last)
        keys = subprocess.run(["tmux", "-S", str(cell / "tty.sock"), "list-keys", "-T", "root"],
                              capture_output=True, text=True).stdout
        self.assertIn("pick", keys)                                      # Ctrl-] 換一格

    def test_watch_describes_stream(self):
        cell = self.ask(self.tmp / "ws-a", "一")
        (cell / "live.jsonl").write_text("\n".join(json.dumps(e) for e in [
            {"type": "system", "subtype": "init", "session_id": "abcdef0123", "model": "haiku"},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "我看看"},
                                                          {"type": "tool_use", "name": "Read", "input": {"file_path": "a"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "內容"}]}},
            {"type": "result", "is_error": False, "result": "好了", "total_cost_usd": 0.001}]) + "\n")
        r = self.hub("watch", cwd=self.tmp / "ws-a")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), ["── 開始（對話 abcdef01，模型 haiku）", "我看看",
                                                 '  ▶ Read {"file_path": "a"}', "  ◀ 內容", "── 結束（完成，0.0010 美元）"])


if __name__ == "__main__":
    unittest.main()
