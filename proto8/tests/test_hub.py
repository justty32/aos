"""test_hub - proto8/extras/cli_hub（10-30 版）：常駐 aos-hub-kernel、aos-hub 的 add／open／close／stop／ls／state／watch，
kernel 經 <資料夾>/.stack/queue/（N-16 有順序信箱）收訊息、user／assistant 各接一行進 .stack/history.jsonl，
cli_session 在小格建 transcripts/<kind>-<id>.jsonl symlink、stop 換成複製（10-30 agent-lifecycle 第 6 步）。

用 test_fay 的假 claude（多寫一份 $CLAUDE_CONFIG_DIR/projects/<資料夾>/<id>.jsonl 當 CLI 自己的對話檔），不花額度；
要 tmux（沒有就 skip 畫面那個）。
對它說話現在先用 aos-post 直接投信（say）、讀 history 最新那則沒有 tool_calls 的 assistant（listen）；
aos-say／aos-listen 改走 queue（agent-lifecycle 第 4 步）合進來後，say／listen 這兩個 helper 換成經它們、
再補「cd 過去不給 --ws」「listen --status 看到 aos-hub-kernel」「listen 說得出哪封失敗」三案。
設計：proto8/thinking/2026-10-28-hub-adapter.md、2026-10-30-agent-lifecycle.md。"""
import json, os, shutil, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, IMPLS, path_with  # noqa: E402
from test_fay import FAKE_CLAUDE, SYS_PATH, HAS_TMUX  # noqa: E402
BIN = ROOT / "extras" / "cli_hub" / "bin"
POST = IMPLS / "aos-post" / "bin"                                       # kernel 叫 aos-post（叫的人放 PATH）
TOOL = ROOT / "lib" / "agent" / "claude"
CLEAR = ("AOS_HUB", "AOS_WS", "AOS_ENTRY", "AOS_STACK", "TMUX", "CLAUDE_CONFIG_DIR", "CODEX_HOME")
# 假 claude 多做一件真的 claude 會做的事：把對話存在 $CLAUDE_CONFIG_DIR/projects/<cwd 編碼>/<id>.jsonl（一次接一行）
SAVE = """if os.environ.get("CLAUDE_CONFIG_DIR"):
    _d = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "projects", os.getcwd().replace("/", "-"))
    os.makedirs(_d, exist_ok=True)
    with open(os.path.join(_d, sid + ".jsonl"), "a") as _f:
        _f.write(json.dumps({"argv": a}) + "\\n")
"""
assert FAKE_CLAUDE.count('if "-p" in a:') == 1
FAKE = FAKE_CLAUDE.replace('if "-p" in a:', SAVE + 'if "-p" in a:')


class Hub(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hub-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.bin / "claude").write_text(FAKE)
        (self.bin / "claude").chmod(0o755)
        self.log = self.tmp / "cli.log"
        self.tool = self.tmp / "tools" / "claude"                        # 複製工具，cli.json 等回答改 15 秒
        shutil.copytree(TOOL, self.tool)
        cfg = json.loads((self.tool / "cli.json").read_text())
        (self.tool / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
        os.symlink(ROOT / "lib" / "agent" / "cli_session.py", self.tmp / "tools" / "cli_session.py")
        self.hubdir = self.tmp / "hub"
        self.home = self.tmp / "claude-home"                              # CLAUDE_CONFIG_DIR：不碰使用者的 ~/.claude
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
        e.update(PATH=path_with(os.pathsep.join([str(self.bin), str(POST), SYS_PATH])), FAKE_LOG=str(self.log),
                 CLAUDE_CONFIG_DIR=str(self.home))
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
        """＝aos-say 第 4 步之後做的事：aos-post send --ordered <stack>/queue，body 是一則 user message；回信號。"""
        r = self.run_([POST / "aos-post", "send", "--ordered", ws / ".stack" / "queue"],
                      input=json.dumps({"role": "user", "content": text}))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def history(self, ws):
        p = ws / ".stack" / "history.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    def listen(self, ws, sig, timeout=20):
        """＝aos-listen 第 4 步之後的規則：信還在 queue 的 new/ 或 cur/ 就等；不見了印 history 最新那則沒有 tool_calls 的 assistant。"""
        q = ws / ".stack" / "queue"
        deadline = time.time() + timeout
        while (q / "new" / sig).exists() or (q / "cur" / sig).exists():
            if time.time() > deadline:
                self.fail("%s 一直沒答完" % sig)
            time.sleep(0.05)
        last = [m for m in self.history(ws) if m.get("role") == "assistant" and not m.get("tool_calls")]
        self.assertTrue(last, "history 沒有 assistant")
        return last[-1]["content"] + "\n"

    def trace(self, ws):
        p = ws / ".stack" / "trace.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

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
        box = w / ".stack"
        self.assertEqual(sorted(os.listdir(box / "queue")), ["cur", "new", "tmp"])   # add＝aos-post init（10-30 A-2）
        n1 = self.say(w, "你好")
        a = self.listen(w, n1)
        sid = (w / ".stack" / "claude" / "session.txt").read_text().strip()
        self.assertEqual(a, "fake claude[%s]: 你好\n" % sid[:8])
        n2 = self.say(w, "再一句")
        self.assertIn("再一句", self.listen(w, n2))
        argv = self.last_argv()
        self.assertEqual((argv[argv.index("--resume") + 1], "-p" in argv), (sid, True))    # 同一段對話續著
        self.assertEqual(self.history(w), [                              # user、assistant 各一行（P-41）
            {"role": "user", "content": "你好"}, {"role": "assistant", "content": "fake claude[%s]: 你好" % sid[:8]},
            {"role": "user", "content": "再一句"}, {"role": "assistant", "content": "fake claude[%s]: 再一句" % sid[:8]}])
        self.assertEqual((os.listdir(box / "queue" / "new"), os.listdir(box / "queue" / "cur")), ([], []))   # 答完就收信
        self.assertFalse((box / "out").exists())                         # 沒有 out/（A-6）
        self.assertEqual(sorted(os.listdir(w)), [".stack"])              # 資料夾本身不長東西
        self.assertEqual([(t["state"], t["question"], t["code"]) for t in self.trace(w)],
                         [("aos-hub-kernel", n1, 0), ("aos-hub-kernel", n2, 0)])
        self.assertEqual((box / "server.txt").read_text().split()[1], "aos-hub-kernel")   # listen --status 靠它
        self.assertEqual(len((box / "claude" / "live.jsonl").read_text().splitlines()), 2)   # 只接不重寫
        self.assertEqual(self.ls()[0]["state"], "收起了")
        self.assertIn(sid, self.hub("state", cwd=w).stdout)

    def test_agent_cells_are_listed_not_served(self):
        self.start_kernel()
        w = self.ws("ws-agent")
        cell = w / ".stack" / "act" / "claude"
        self.assertEqual(self.run_([POST / "aos-post", "init", w / ".stack" / "queue"]).returncode, 0)
        r = self.run_([self.tool / "_entry"], input=json.dumps({"prompt": "agent 叫的"}),
                      env=self.env(dict(AOS_WS=str(w), AOS_STACK=str(cell) + "/")))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([(x["cell"], x["state"]) for x in self.ls()], [(str(cell), "收起了（只登記）")])
        sid = (cell / "session.txt").read_text().strip()
        link = cell / "transcripts" / ("claude-%s.jsonl" % sid)          # agent 叫的工具格也建 symlink（方向題 3）
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)).name, sid + ".jsonl")
        n = self.say(w, "這題是 agent 的")                              # 在 .stack/queue 放一封：kernel 不替只登記的收
        time.sleep(1.2)
        self.assertTrue((w / ".stack" / "queue" / "new" / n).exists())

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
        letter = w / ".stack" / "queue" / "cur" / n / "letter.json"
        self.assertTrue(letter.exists())                                 # 信留在 cur/（P-20）
        t = self.trace(w)[-1]                                            # listen 靠 trace 說得出卡在哪封
        self.assertEqual((t["question"], t["code"]), (n, 1))
        self.assertIn("claude: CliFailed", t["error"])
        self.assertEqual(self.history(w), [{"role": "user", "content": "boom"}])
        time.sleep(0.8)
        self.assertEqual(len(self.history(w)), 1)                        # 出錯了就不再收、不重接
        d = json.loads(letter.read_text())                               # 人修好、close 一次＝重新收題
        letter.write_text(json.dumps(dict(d, body={"role": "user", "content": "修好了"})))
        self.assertEqual(self.hub("close", w).returncode, 0)
        self.assertIn("修好了", self.listen(w, n))
        self.assertEqual([m["content"][:3] for m in self.history(w)], ["boo", "修好了", "fak"])

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_open_close_stop(self):
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
        r = self.hub("close", "--idle", "60")                            # 還沒閒那麼久：不收
        self.assertEqual((r.returncode, r.stdout, self.ls()[0]["state"]), (0, "", "畫面開著"), r.stderr)
        r = self.hub("close", cwd=w)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "收起了"), r.stderr)
        self.assertEqual(self.ls()[0]["state"], "收起了")
        self.assertIn("又一句", self.listen(w, self.say(w, "又一句")))     # 收起＝--resume 問一次
        argv = self.last_argv()
        self.assertEqual((argv[argv.index("--resume") + 1], "-p" in argv), (sid, True))
        r = self.hub("open", "-d", cwd=w)                                # 叫回
        self.assertIn("叫回", r.stdout)
        self.assertTrue((cell / "transcripts" / ("claude-%s.jsonl" % sid)).is_symlink())
        r = self.hub("stop", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        arch = list((w / ".stack" / "hub_archive").iterdir())
        self.assertEqual(len(arch), 1)
        self.assertEqual((arch[0] / "session.txt").read_text().strip(), sid)
        kept = arch[0] / "transcripts" / ("claude-%s.jsonl" % sid)
        self.assertTrue(kept.is_file() and not kept.is_symlink())       # stop：symlink 換成真的複製
        self.assertFalse(cell.exists())
        self.assertFalse((w / ".stack" / "server.txt").exists())
        self.assertEqual(self.ls(), [])
        self.assertEqual(self.code(self.hub("state", cwd=w)), (1, "InstanceMissing"))

    def test_transcript_link_then_copy(self):
        """add 後答過一句：小格有 symlink 指到 CLI 自己的對話檔；stop 後 hub_archive/.../transcripts/ 是真檔（10-30 C-15～C-17）。"""
        self.start_kernel()
        w = self.ws()
        self.hub("add", "--tool", self.tool, w)
        cell = w / ".stack" / "claude"
        self.listen(w, self.say(w, "一"))
        sid = (cell / "session.txt").read_text().strip()
        link = cell / "transcripts" / ("claude-%s.jsonl" % sid)
        src = self.home / "projects" / str(w).replace("/", "-") / (sid + ".jsonl")
        self.assertEqual((link.is_symlink(), os.readlink(link)), (True, str(src)))
        self.listen(w, self.say(w, "二"))
        self.assertEqual(len(link.read_text().splitlines()), 2)          # symlink 永遠是最新的
        self.assertIn("對話檔 %s → %s" % (link, src), self.hub("state", cwd=w).stdout)
        self.assertFalse(self.ls()[0]["transcript_missing"])
        r = self.hub("stop", w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("含 CLI 的對話 1 份", r.stdout)
        kept = next((w / ".stack" / "hub_archive").iterdir()) / "transcripts" / link.name
        self.assertTrue(kept.is_file() and not kept.is_symlink())
        src.write_text("CLI 自己清掉以前改過\n")                         # 複製的不再跟著變
        self.assertEqual(len(kept.read_text().splitlines()), 2)

    def test_transcript_gone_is_said(self):
        """symlink 目標被 CLI 自己清掉：state／ls 說一句、退 0、不補（10-30 C-16）。"""
        self.start_kernel()
        w = self.ws()
        self.hub("add", "--tool", self.tool, w)
        self.listen(w, self.say(w, "一"))
        sid = (w / ".stack" / "claude" / "session.txt").read_text().strip()
        shutil.rmtree(self.home / "projects")
        r = self.hub("state", cwd=w)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CLI 自己的對話檔已不在", r.stdout)
        r = self.hub("ls")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CLI 自己的對話檔已不在", r.stdout)
        self.assertTrue(self.ls()[0]["transcript_missing"])
        self.assertIn("再一句", self.listen(w, self.say(w, "再一句")))    # 不擋正事
        self.assertTrue((w / ".stack" / "claude" / "transcripts" / ("claude-%s.jsonl" % sid)).is_symlink())

    def test_bad_letter_dropped(self):
        """queue 只收 OpenAI message 物件（衝突 5）：不是的＝壞信，丟掉、trace 記 letter_warning、不算出錯。"""
        self.start_kernel()
        w = self.ws()
        self.hub("add", "--tool", self.tool, w)
        r = self.run_([POST / "aos-post", "send", "--ordered", w / ".stack" / "queue"], input=json.dumps("純文字"))
        n = r.stdout.strip()
        self.assertIn("好", self.listen(w, self.say(w, "好")))
        self.assertFalse((w / ".stack" / "queue" / "cur" / n).exists())
        t = [x for x in self.trace(w) if x["question"] == n]
        self.assertEqual((len(t), t[0]["code"]), (1, 0))
        self.assertIn("role", t[0]["letter_warning"])
        self.assertEqual([m["role"] for m in self.history(w)], ["user", "assistant"])
        self.assertEqual(self.ls()[0]["state"], "收起了")

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
