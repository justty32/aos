"""test_hub - proto8/extras/cli_hub（10-28 版）：常駐 aos-hub-kernel、aos-hub 的 add／open／pause／stop／ls／state／watch，
以及 aos-say／aos-listen 經 kernel 對 claude 說話（agent 對話協議，CONVENTION P-11～P-14）。

用 test_fay 的假 claude，不花額度；要 tmux（沒有就 skip 畫面那個）。
設計：proto8/thinking/2026-10-28-hub-adapter.md。"""
import json, os, shutil, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, path_with  # noqa: E402
from test_fay import FAKE_CLAUDE, SYS_PATH, HAS_TMUX  # noqa: E402
BIN = ROOT / "extras" / "cli_hub" / "bin"
HUMAN = ROOT / "extras" / "human" / "bin"
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
        self.tool = self.tmp / "tools" / "claude"                        # 複製工具，cli.json 等回答改 15 秒
        shutil.copytree(TOOL, self.tool)
        cfg = json.loads((self.tool / "cli.json").read_text())
        (self.tool / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
        os.symlink(ROOT / "lib" / "agent" / "cli_session.py", self.tmp / "tools" / "cli_session.py")
        self.hubdir = self.tmp / "hub"
        self.socks = []
        self.kernel = None
        self.addCleanup(self.kill_all)

    def kill_all(self):
        if self.kernel and self.kernel.poll() is None:
            self.kernel.terminate()
            self.kernel.wait(10)
        if self.kernel:
            self.kernel.stderr.close()
        for s in self.socks:
            subprocess.run(["tmux", "-S", str(s), "kill-server"], capture_output=True)

    def env(self, extra=None, hub=True):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH=path_with(str(self.bin) + os.pathsep + SYS_PATH), FAKE_LOG=str(self.log))
        if hub:
            e["AOS_HUB"] = str(self.hubdir)
        e.update(extra or {})
        return e

    def start_kernel(self):
        self.kernel = subprocess.Popen([str(BIN / "aos-hub-kernel")], env=self.env(), stdin=subprocess.DEVNULL,
                                       stderr=subprocess.PIPE, text=True)
        for _ in range(100):
            if (self.hubdir / "kernel.sock").exists():
                return
            time.sleep(0.05)
        self.fail("kernel 沒開起來：%s" % self.kernel.stderr.read())

    def run_(self, argv, cwd=None, env=None, timeout=60, input=None):
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True, env=env or self.env(), cwd=cwd,
                              input=input, stdin=None if input is not None else subprocess.DEVNULL, timeout=timeout)

    def hub(self, *args, cwd=None):
        return self.run_([BIN / "aos-hub", *args], cwd=cwd)

    def ls(self):
        r = self.hub("ls", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def ws(self, name="ws-a"):
        w = self.tmp / name
        w.mkdir(exist_ok=True)
        self.socks.append(w / ".stack" / "claude" / "tty.sock")
        return w

    def say(self, ws, text):
        r = self.run_([HUMAN / "aos-say", "--ws", ws, text])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def listen(self, ws, name):
        r = self.run_([HUMAN / "aos-listen", "--ws", ws, "--timeout", "20", name])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def code(self, r):
        return (r.returncode, (r.stderr.split() + ["", ""])[1])

    def last_argv(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()][-1]["argv"]

    def test_hub_and_kernel_required(self):
        r = self.run_([BIN / "aos-hub", "ls"], env=self.env(hub=False))
        self.assertEqual(self.code(r), (1, "HubMissing"))
        r = self.run_([BIN / "aos-hub-kernel"], env=self.env(hub=False))
        self.assertEqual(self.code(r), (1, "HubMissing"))
        r = self.hub("ls")                                               # 有 AOS_HUB、kernel 沒在跑：報錯
        self.assertEqual(self.code(r), (1, "KernelMissing"))
        self.start_kernel()
        r = self.run_([BIN / "aos-hub-kernel"], timeout=10)              # 第二個
        self.assertEqual(self.code(r), (1, "KernelBusy"))
        self.assertEqual(self.ls(), [])
        r = self.hub("state", cwd=self.tmp)
        self.assertEqual(self.code(r), (1, "InstanceMissing"))
        r = self.hub("bogus")
        self.assertEqual(self.code(r), (1, "ArgumentsBad"))

    def test_say_listen_through_hub(self):
        self.start_kernel()
        w = self.ws()
        r = self.hub("add", "--tool", self.tool, w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(w / ".stack" / "claude"))
        a = self.listen(w, self.say(w, "你好"))
        sid = (w / ".stack" / "claude" / "session.txt").read_text().strip()
        self.assertEqual(a, "fake claude[%s]: 你好\n" % sid[:8])
        self.assertIn("再一句", self.listen(w, self.say(w, "再一句")))
        argv = self.last_argv()
        self.assertEqual((argv[argv.index("--resume") + 1], "-p" in argv), (sid, True))    # 同一段對話續著
        self.assertEqual(sorted(os.listdir(w / "done")), sorted(os.listdir(w / "out")))
        trace = [json.loads(l) for l in (w / ".stack" / "trace.jsonl").read_text().splitlines()]
        self.assertEqual([(t["state"], t["code"]) for t in trace], [("aos-hub-kernel", 0)] * 2)
        st = self.run_([HUMAN / "aos-listen", "--ws", w, "--status"])
        self.assertIn("aos-hub-kernel", st.stdout)                       # server.txt：listen 知道有人在服務
        self.assertEqual(len((w / ".stack" / "claude" / "live.jsonl").read_text().splitlines()), 2)   # 只接不重寫
        self.assertEqual(self.ls()[0]["state"], "收起了")
        self.assertIn(sid, self.hub("state", cwd=w).stdout)

    def test_agent_cells_are_listed_not_served(self):
        self.start_kernel()
        w = self.ws("ws-agent")
        cell = w / ".stack" / "act" / "claude"
        r = self.run_([self.tool / "_entry"], input=json.dumps({"prompt": "agent 叫的"}),
                      env=self.env(dict(AOS_WS=str(w), AOS_STACK=str(cell) + "/")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([(x["cell"], x["state"]) for x in self.ls()], [(str(cell), "收起了（只登記）")])
        (w / "new").mkdir()
        (w / "new" / "q.txt").write_text("這題是 agent 的")
        time.sleep(1.2)
        self.assertTrue((w / "new" / "q.txt").exists())                  # kernel 不替它收題

    def test_failure_waits_for_human(self):
        self.start_kernel()
        w = self.ws()
        self.hub("add", "--tool", self.tool, w)
        n = self.say(w, "boom")
        for _ in range(100):
            if self.ls()[0]["state"] == "出錯":
                break
            time.sleep(0.1)
        row = self.ls()[0]
        self.assertEqual(row["state"], "出錯")
        self.assertIn("CliFailed", row["error"])
        self.assertTrue((w / "cur" / n).exists())                        # 題目留在 cur/（P-20）
        r = self.run_([HUMAN / "aos-listen", "--ws", w, "--timeout", "1.5", n])
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-hub-kernel 答 %s 失敗：claude: CliFailed" % n, r.stderr)   # listen 說得出卡在哪
        (w / "cur" / n).write_text("修好了")                              # 人修好、pause 一次＝重新收題
        self.assertEqual(self.hub("pause", w).returncode, 0)
        self.assertIn("修好了", self.listen(w, n))

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_open_pause_stop(self):
        self.start_kernel()
        w = self.ws()
        cell = w / ".stack" / "claude"
        r = self.hub("open", "-d", "--tool", self.tool, cwd=w)          # 還沒納管：先 add 再開畫面
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ls()[0]["state"], "畫面開著")
        self.assertEqual(self.listen(w, self.say(w, "畫面上的一句")), "fake live: 畫面上的一句\n")   # 畫面開著＝打進畫面
        keys = subprocess.run(["tmux", "-S", str(cell / "tty.sock"), "list-keys", "-T", "root"],
                              capture_output=True, text=True).stdout
        self.assertIn("C-]", keys)                                       # Ctrl-] 只跳出
        sid = (cell / "session.txt").read_text().strip()
        r = self.hub("pause", "--idle", "60")                            # 還沒閒那麼久：不收
        self.assertEqual((r.returncode, r.stdout, self.ls()[0]["state"]), (0, "", "畫面開著"), r.stderr)
        r = self.hub("pause", cwd=w)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "收起了"), r.stderr)
        self.assertEqual(self.ls()[0]["state"], "收起了")
        self.assertIn("又一句", self.listen(w, self.say(w, "又一句")))     # 收起＝--resume 問一次
        argv = self.last_argv()
        self.assertEqual((argv[argv.index("--resume") + 1], "-p" in argv), (sid, True))
        r = self.hub("open", "-d", cwd=w)                                # 叫回
        self.assertIn("叫回", r.stdout)
        r = self.hub("stop", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        arch = list((w / ".stack" / "hub_archive").iterdir())
        self.assertEqual(len(arch), 1)
        self.assertEqual((arch[0] / "session.txt").read_text().strip(), sid)
        self.assertFalse(cell.exists())
        self.assertFalse((w / ".stack" / "server.txt").exists())
        self.assertEqual(self.ls(), [])
        self.assertEqual(self.code(self.hub("state", cwd=w)), (1, "InstanceMissing"))

    def test_watch_follows_live(self):
        self.start_kernel()
        w = self.ws()
        self.hub("add", "--tool", self.tool, w)
        self.listen(w, self.say(w, "一"))
        live = w / ".stack" / "claude" / "live.jsonl"
        p = subprocess.Popen([str(BIN / "aos-hub"), "watch"], cwd=w, env=self.env(), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        time.sleep(0.8)
        with open(live, "a") as f:
            f.write("\n".join(json.dumps(e) for e in [
                {"type": "system", "subtype": "init", "session_id": "abcdef0123", "model": "haiku"},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "我看看"},
                                                              {"type": "tool_use", "name": "Read", "input": {"file_path": "a"}}]}},
                {"type": "user", "message": {"content": [{"type": "tool_result", "content": "內容"}]}},
                {"type": "result", "is_error": False, "result": "好了", "total_cost_usd": 0.001}]) + "\n")
        out, _ = p.communicate(timeout=10)
        self.assertEqual(out.splitlines(), ["── 開始（對話 abcdef01，模型 haiku）", "我看看",
                                            '  ▶ Read {"file_path": "a"}', "  ◀ 內容", "── 結束（完成，0.0010 美元）"])


if __name__ == "__main__":
    unittest.main()
