"""test_eca_turn - proto8/bin/aos-eca-turn（10-31 前是 lib/eca/turn 格）：外部 coding agent（claude／codex）的一輪——從 stack 的
queue 認領全部（11-03 起一批一次：cur/ 與 new/ 的信照順序一起丟進一次 CLI）、交給 CLI 就收信（11-03，eca 20）、回答接進 history（eca B 結論 2 的 ①～⑦、實作第 4 步）；--one 工具形（stdin {"prompt"} → stdout）；
10-31 的 --on-empty（取代 ECA_ON_EMPTY）與 --on-busy（yield｜answer）。

用 test_cli_tools 的假 claude／codex，不花額度；畫面那條路大多是 cli_session 的、test_cli_tools 測，這裡只測 --on-busy answer 碰畫面的兩案
（真 tmux＋假 claude；沒 tmux 就 skip）。
設計：proto8/thinking/2026-10-30-eca.md。"""
import fcntl, json, os, pty, select, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
from test_cli_tools import FAKE_CLAUDE, FAKE_CODEX, SYS_PATH, HAS_TMUX  # noqa: E402
TURN = ROOT / "bin" / "aos-eca-turn"
CLI_SESSION = ROOT / "lib" / "agent" / "cli_session.py"
SAY = ROOT / "extras" / "human" / "bin" / "aos-say"
POST = tool("aos-post")
# 探針 CLI（test_finished_when_handed）：題目讀完之後（交出去的那一刻起）等這批信被收掉，記下當時的 queue 與 history，
# 再把題目原樣交給真的假 CLI 答
PROBE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time
prompt = sys.stdin.read()
box, end = %(box)r, time.time() + 10
ls = lambda s: sorted(n for n in os.listdir(os.path.join(box, s)) if not n.startswith("."))
while (ls("cur") or ls("new")) and time.time() < end:
    time.sleep(0.05)
with open(%(hist)r) as f:
    roles = [json.loads(l)["role"] for l in f if l.strip()]
with open(%(out)r, "w") as f:
    json.dump({"cur": ls("cur"), "new": ls("new"), "roles": roles}, f)
sys.exit(subprocess.run([%(real)r] + sys.argv[1:], input=prompt, text=True).returncode)
'''
CLEAR = ("AOS_HUB", "AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CD", "AOS_CF", "AOS_CO", "TMUX", "ECA_ON_EMPTY",
         "CLAUDE_CONFIG_DIR", "CODEX_HOME", "FAKE_TRANSCRIPTS")


class Turn(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eca-turn-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, src in (("claude", FAKE_CLAUDE), ("codex", FAKE_CODEX)):
            (self.bin / name).write_text(src)
            (self.bin / name).chmod(0o755)
        self.log = self.tmp / "cli.log"
        self.defs = {}
        for kind in ("claude", "codex"):                                  # 定義＝頂層 cli.json（從 lib/agent 的工具抄、等回答改 15 秒）
            d = self.tmp / ("eca-" + kind)
            d.mkdir()
            cfg = json.loads((ROOT / "lib" / "agent" / kind / "cli.json").read_text())
            (d / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
            self.defs[kind] = d
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.stack = self.ws / ".stack"
        self.box = self.stack / "queue"

    def env(self, extra=None):
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH=path_with(str(self.bin) + os.pathsep + SYS_PATH), FAKE_LOG=str(self.log),
                 AOS_WS=str(self.ws), AOS_STACK=str(self.stack) + "/", FAKE_TRANSCRIPTS="1",
                 CLAUDE_CONFIG_DIR=str(self.tmp / "claude-home"), CODEX_HOME=str(self.tmp / "codex-home"))
        e.update(extra or {})
        return e

    def argv(self, kind="claude", flags=()):
        return [str(TURN)] + list(flags) + [str(self.defs[kind])]

    def turn(self, kind="claude", extra=None, flags=(), input=None):
        return subprocess.run(self.argv(kind, flags), input=input, capture_output=True,
                              text=True, env=self.env(extra), timeout=60,
                              stdin=None if input is not None else subprocess.DEVNULL)

    def turn_bg(self, flags=()):
        """背景跑一次（等它卡住時用）：stdin 關掉、輸出收起來。"""
        p = subprocess.Popen(self.argv("claude", flags), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=self.env())
        self.addCleanup(lambda: p.poll() is None and p.kill())
        return p

    def say(self, text):
        r = subprocess.run([str(SAY), "--stack", str(self.stack), text], capture_output=True, text=True,
                           env=self.env(), timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def post(self, *args, input=""):
        r = subprocess.run([POST] + list(args), input=input, capture_output=True, text=True, env=self.env(), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def history(self):
        p = self.stack / "history.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []

    def no_trace(self):
        """11-03 起不寫 trace.jsonl（使用者「整個拿掉」）。"""
        self.assertFalse((self.stack / "trace.jsonl").exists())

    def stage(self, s):
        d = self.box / s
        return sorted(n for n in os.listdir(d) if not n.startswith(".")) if d.exists() else []

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def sid(self, kind="claude"):
        return (self.stack / kind / "session.txt").read_text().strip()

    # ------------------------------------------------------------ 平級形

    def test_say_then_turn(self):
        """say 一封、turn 一次：history 多 user＋assistant 兩則、信不見、沒有 trace.jsonl、eca.json、transcripts symlink；再一封續同一段對話。"""
        self.say("你好")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        sid = self.sid()
        self.assertEqual(self.history(), [{"role": "user", "content": "你好"},
                                          {"role": "assistant", "content": "fake claude[%s]: 你好" % sid[:8]}])
        self.assertEqual((self.stage("new"), self.stage("cur")), ([], []))
        self.assertFalse((self.stack / "current.txt").exists())
        self.no_trace()
        self.assertEqual(json.loads((self.stack / "eca.json").read_text()),
                         {"kind": "claude", "ws": str(self.ws), "template": str(self.defs["claude"])})
        self.assertEqual(self.calls()[0]["cwd"], str(self.ws))                 # CLI 在工作區裡跑
        self.assertTrue((self.stack / "claude" / "transcripts" / ("claude-%s.jsonl" % sid)).is_symlink())
        self.say("再一句")
        self.assertEqual(self.turn().returncode, 0)
        argv = self.calls()[-1]["argv"]
        self.assertEqual(argv[argv.index("--resume") + 1], sid)
        self.assertEqual(len(self.history()), 4)

    def test_tools(self):
        """11-03 eca-tools 平級形：定義放 tools.json（cli.json 沒寫 tools＝用它）＝claude argv 多 --mcp-config <stack>/claude/mcp.json
        --allowedTools mcp__aos，mcp.json 的 --ws＝$AOS_WS、--stack＝$AOS_STACK（那隻 eca 的 stack，不是 CLI 小格）、tools_flags 原樣夾在中間；
        codex＝兩個 -c。tools 指的檔不在＝ToolsMissing 退 1、信留著。"""
        reg = self.defs["claude"] / "tools.json"
        reg.write_text(json.dumps({"tools": {"clock": {"path": str(ROOT / "lib" / "base" / "clock")}}}))
        cfg = json.loads((self.defs["claude"] / "cli.json").read_text())
        (self.defs["claude"] / "cli.json").write_text(json.dumps(dict(cfg, tools_flags=["--timeout-s", "120"])))
        self.say("幾點")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        argv = self.calls()[-1]["argv"]
        mcp = self.stack / "claude" / "mcp.json"
        self.assertEqual(argv[argv.index("--mcp-config") + 1], str(mcp))
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "mcp__aos")
        self.assertEqual(json.loads(mcp.read_text())["mcpServers"]["aos"]["args"],
                         ["--ws", str(self.ws), "--stack", str(self.stack), "--timeout-s", "120", str(reg)])
        self.assertEqual((self.stack / "claude" / "stack.txt").read_text().strip(), str(self.stack))
        creg = self.defs["codex"] / "tools.json"
        creg.write_text(reg.read_text())
        self.say("codex 幾點")
        r = self.turn("codex")
        self.assertEqual(r.returncode, 0, r.stderr)
        argv = self.calls()[-1]["argv"]
        args = next(a for a in argv if a.startswith("mcp_servers.aos.args="))
        self.assertEqual(json.loads(args.partition("=")[2]), ["--ws", str(self.ws), "--stack", str(self.stack), str(creg)])
        self.assertIn('mcp_servers.aos.command="aos-mcp"', argv)
        (self.defs["claude"] / "cli.json").write_text(json.dumps(dict(cfg, tools="gone.json")))
        sig = self.say("登記檔不在")
        r = self.turn()
        self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-eca-turn:", "ToolsMissing"]), r.stderr)
        self.assertEqual(self.stage("new"), [sig])

    def test_codex(self):
        self.say("codex 你好")
        r = self.turn("codex")
        self.assertEqual(r.returncode, 0, r.stderr)
        thread = self.sid("codex")
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": "fake codex[%s]: codex 你好" % thread[:8]})
        self.assertEqual(json.loads((self.stack / "eca.json").read_text())["kind"], "codex")

    def test_cur_first(self):
        """cur/ 有認領了、還沒交出去的（上次 yield 退讓或 CLI 沒起來；history 沒動）＝跟 new/ 那封同一批一起答（一次 CLI），
        user 各接一次；下一次 queue 空退 10。"""
        first = self.say("第一封")
        self.say("第二封")
        self.post("init", str(self.box))
        self.assertEqual(self.post("take", str(self.box)), first)
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([m["role"] for m in self.history()], ["user", "user", "assistant"])
        self.assertEqual([m["content"] for m in self.history()][:2], ["第一封", "第二封"])
        self.assertTrue(self.history()[-1]["content"].endswith(": 第一封\n\n第二封"), self.history()[-1])
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual((self.stage("new"), self.stage("cur")), ([], []))
        self.assertEqual(self.turn().returncode, 10)

    def test_finished_when_handed(self):
        """11-03（使用者「對於eca來說，他收到信後，丟給claude之類的，然後這封信就算是完成了」）：CLI 還在跑的時候
        這批信已經收掉（cur/、new/ 都空）、user 已接進 history、還沒有 assistant；答完才接 assistant。claude、codex 都一樣。"""
        probe = self.tmp / "probe.json"
        for kind in ("claude", "codex"):
            real = self.bin / ("real-" + kind)
            os.replace(self.bin / kind, real)
            (self.bin / kind).write_text(PROBE % {"real": str(real), "box": str(self.box), "hist": str(self.stack / "history.jsonl"),
                                                  "out": str(probe)})
            (self.bin / kind).chmod(0o755)
            self.say(kind + " 一")
            self.say(kind + " 二")
            n = len(self.history())
            r = self.turn(kind)
            self.assertEqual(r.returncode, 0, r.stderr)
            seen = json.loads(probe.read_text())
            self.assertEqual((seen["cur"], seen["new"]), ([], []), kind)
            self.assertEqual(seen["roles"][n:], ["user", "user"], kind)
            self.assertEqual([m["role"] for m in self.history()][n:], ["user", "user", "assistant"], kind)

    def test_bad_letter_dropped(self):
        """body 不是 {"role": "user", "content": 非空字串}＝壞信：丟掉、mailbox_warning.txt 記最後一封（11-03 前記在 trace）、退 0、不問 CLI；
        11-03 起一批：四封壞信一輪全丟。"""
        self.post("init", str(self.box))
        bad = []
        for body in ({"text": "沒有 role"}, "純文字", {"role": "user", "content": ""}, {"role": "assistant", "content": "x"}):
            bad.append(self.post("send", "--ordered", str(self.box), input=json.dumps(body)))
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.stage("new"), self.stage("cur")), ([], []))
        self.assertEqual(self.history(), [])
        self.assertEqual(self.calls(), [])
        self.assertTrue((self.stack / "mailbox_warning.txt").read_text().startswith("信 %s 不採用：" % bad[-1]))
        self.no_trace()

    def test_batch_in_order(self):
        """11-03（使用者「每次aos-eca-turn就是把所有信一起丟進去(當然，是有順序的)」「一批幾封無上限」）：一輪把 queue 的信照順序
        一起丟進一次 CLI——history 每封一則 user、接一則 assistant；content 用一個空行接起來；中間的壞信丟掉、不擋其他封。"""
        self.say("一")
        self.post("send", "--ordered", str(self.box), input=json.dumps({"text": "壞"}))
        self.say("二")
        self.say("三")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.calls()), 1)
        h = self.history()
        self.assertEqual([(m["role"], m["content"]) for m in h[:3]], [("user", "一"), ("user", "二"), ("user", "三")])
        self.assertEqual(h[3], {"role": "assistant", "content": "fake claude[%s]: 一\n\n二\n\n三" % self.sid()[:8]})
        self.assertEqual((self.stage("new"), self.stage("cur")), ([], []))
        self.assertIn("不採用", (self.stack / "mailbox_warning.txt").read_text())
        self.assertEqual(self.turn().returncode, 10)

    def test_unordered_last(self):
        """11-03 aos-post 改版（有序、無序同箱）：名字不是有序的不再是壞信——無序的排在這批最後（aos_ws.letter_key：有序先、無序後，
        各照名字；名字照字面比比有序的小也一樣），照樣答。"""
        self.post("init", str(self.box))
        self.post("send", str(self.box), "0-unordered", input=json.dumps({"role": "user", "content": "無序"}))
        self.say("一")
        self.say("二")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.calls()), 1)
        h = self.history()
        self.assertEqual([m["content"] for m in h[:3]], ["一", "二", "無序"])
        self.assertTrue(h[3]["content"].endswith(": 一\n\n二\n\n無序"), h[3])
        self.assertEqual((self.stage("new"), self.stage("cur")), ([], []))
        self.assertFalse((self.stack / "mailbox_warning.txt").exists())

    def test_empty_stop_idle(self):
        """queue 空：--on-empty 沒給／stop＝退 10、idle＝退 0，（10-31 從 ECA_ON_EMPTY 改 argv）。"""
        self.assertEqual(self.turn().returncode, 10)
        self.assertEqual(self.turn(flags=["--on-empty", "stop"]).returncode, 10)
        self.assertEqual(self.turn(flags=["--on-empty=idle"]).returncode, 0)
        self.assertTrue(all((self.box / s).is_dir() for s in ("tmp", "new", "cur")))   # queue 先建好，say／listen 認得

    def test_eca_on_empty_env_ignored(self):
        """ECA_ON_EMPTY 不再讀：設 idle 照樣是預設 stop（退 10）、設壞值也不錯；--on-empty 才算。"""
        self.assertEqual(self.turn(extra=dict(ECA_ON_EMPTY="idle")).returncode, 10)
        r = self.turn(extra=dict(ECA_ON_EMPTY="maybe"))
        self.assertEqual((r.returncode, r.stderr), (10, ""))
        self.assertEqual(self.turn(extra=dict(ECA_ON_EMPTY="stop"), flags=["--on-empty", "idle"]).returncode, 0)

    def test_flags_bad(self):
        """argv 錯＝ArgumentsBad（不認得的旗標 FlagUnknown）、退 1、不碰 stack：--on-empty／--on-busy 壞值或缺值、--one 帶 --on-empty、
        旗標放在定義資料夾後面、多給位置參數。"""
        d = str(self.defs["claude"])
        for argv, code in ((["--on-empty", "maybe", d], "ArgumentsBad"), (["--on-busy", "skip", d], "ArgumentsBad"),
                           (["--one", "--on-empty", "stop", d], "ArgumentsBad"), ([d, "--one"], "ArgumentsBad"),
                           ([d, d], "ArgumentsBad"), ([], "ArgumentsBad"), (["--on-busy"], "ArgumentsBad"),
                           (["--maybe", d], "FlagUnknown")):
            r = subprocess.run([str(TURN)] + argv, capture_output=True, text=True, env=self.env(), timeout=30,
                               input=json.dumps({"prompt": "x"}))
            self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-eca-turn:", code]), argv)
        self.assertFalse(self.stack.exists())
        self.assertEqual(self.calls(), [])

    def test_opening_prompt(self):
        """history 空、queue 空、定義有 prompt.txt＝先投開場白再答；答過了（history 不空）就不再投，queue 空退 10。"""
        (self.defs["claude"] / "prompt.txt").write_text("先讀 task.md，照做\n")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.history()[0], {"role": "user", "content": "先讀 task.md，照做"})
        self.assertEqual(self.history()[1]["role"], "assistant")
        self.assertEqual(self.turn().returncode, 10)
        self.assertEqual(len(self.calls()), 1)

    def test_opening_prompt_key(self):
        """11-04：cli.json 的 prompt 指開場白檔（相對路徑從 cli.json 的資料夾算）＝用那份、同層 prompt.txt 不看；
        指的不是檔＝PromptMissing 退 1、不問 CLI；空字串、不是字串＝CfgBad。"""
        d = self.defs["claude"]
        cfg = json.loads((d / "cli.json").read_text())
        (d / "prompt.txt").write_text("不該用這份\n")
        (d / "cli.json").write_text(json.dumps(dict(cfg, prompt="gone.txt")))
        r = self.turn()
        self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-eca-turn:", "PromptMissing"]), r.stderr)
        self.assertEqual(self.calls(), [])
        for bad in ("", 3):
            (d / "cli.json").write_text(json.dumps(dict(cfg, prompt=bad)))
            r = self.turn()
            self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-eca-turn:", "CfgBad"]), r.stderr)
        (d / "tasks").mkdir()
        (d / "tasks" / "open.txt").write_text("照 tasks/open.txt 做\n")
        (d / "cli.json").write_text(json.dumps(dict(cfg, prompt="tasks/open.txt")))
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.history()[0], {"role": "user", "content": "照 tasks/open.txt 做"})
        self.assertEqual(self.turn().returncode, 10)
        self.assertEqual(len(self.calls()), 1)

    def test_session_bad_keeps_letter(self):
        """這段對話有人在用（小格的 lock 被拿著）＝SessionBad：--on-busy 沒給／yield 都退 0、信留 cur/；
        放開後再一次就答，user 不接兩次。"""
        sig = self.say("等一下")
        (self.stack / "claude").mkdir(parents=True)
        with open(self.stack / "claude" / "lock", "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            r = self.turn(flags=["--on-busy", "yield"])
            self.assertEqual(r.returncode, 0, r.stderr)
            r = self.turn()
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.stage("cur"), [sig])
            self.assertEqual(self.history(), [])                                # 還沒交出去：history 不動
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])
        self.assertEqual(self.stage("cur"), [])

    def test_cli_failure_stops(self):
        """CLI 交出去之後失敗（11-03 起）：退 1、stderr「aos-eca-turn: CliFailed」（停下等人）；信已經收了、user 已接、沒有 assistant，
        不自動重答（使用者「中途掛掉就是邊緣狀況，不要讓邊緣狀況影響他的原本意思」）——下一次 queue 空退 10，要重答由人再 say。"""
        self.say("boom")
        self.say("一起的")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-eca-turn: CliFailed "), r.stderr)
        self.assertEqual((self.stage("new"), self.stage("cur")), ([], []))
        self.assertEqual(self.history(), [{"role": "user", "content": "boom"}, {"role": "user", "content": "一起的"}])
        self.assertFalse((self.stack / "current.txt").exists())
        self.assertEqual(self.turn().returncode, 10)
        self.assertEqual(len(self.calls()), 1)
        self.say("再問一次")
        self.assertEqual(self.turn().returncode, 0)
        self.assertEqual([m["role"] for m in self.history()], ["user", "user", "user", "assistant"])

    def test_cli_missing_keeps_batch(self):
        """還沒交出去就錯（CLI 不在 PATH＝CliMissing）：退 1、整批留 cur/、history 不動；裝回來再跑＝整批照問、user 各接一次。"""
        sig = self.say("一")
        sig2 = self.say("二")
        os.replace(self.bin / "claude", self.tmp / "claude.away")
        r = self.turn()
        self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-eca-turn:", "CliMissing"]), r.stderr)
        self.assertEqual(self.stage("cur"), [sig, sig2])
        self.assertEqual(self.history(), [])
        os.replace(self.tmp / "claude.away", self.bin / "claude")
        self.assertEqual(self.turn().returncode, 0)
        self.assertEqual([m["role"] for m in self.history()], ["user", "user", "assistant"])
        self.assertEqual(self.stage("cur"), [])

    def test_args(self):
        r = subprocess.run([str(TURN), "relative/def"], capture_output=True, text=True, env=self.env(),
                           stdin=subprocess.DEVNULL, timeout=30)
        self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-eca-turn:", "AgentBad"]))
        (self.defs["claude"] / "cli.json").unlink()
        self.say("沒有 cli.json")
        r = self.turn()
        self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-eca-turn:", "CfgMissing"]))

    # ------------------------------------------------------------ --on-busy answer（10-31：不因畫面被佔而退讓）

    def until(self, cond, secs=20):
        end = time.time() + secs
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.1)
        return False

    def test_answer_waits_for_lock(self):
        """--on-busy answer：lock 被別人拿著＝等著（不退、信在 cur/），放開後照常答；等的期間寄來的信不進這一批、留給下一輪（11-03）。"""
        sig = self.say("等你放開")
        (self.stack / "claude").mkdir(parents=True)
        held = open(self.stack / "claude" / "lock", "w")
        fcntl.flock(held, fcntl.LOCK_EX)
        p = self.turn_bg(["--on-busy", "answer"])
        self.assertTrue(self.until(lambda: self.stage("cur") == [sig]))
        time.sleep(1)
        self.assertIsNone(p.poll())                                       # 還在等 lock
        self.assertEqual(self.calls(), [])
        later = self.say("等的時候才來")
        held.close()                                                      # 放開
        out, err = p.communicate(timeout=60)
        self.assertEqual(p.returncode, 0, err)
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])
        self.assertEqual((self.stage("cur"), self.stage("new")), ([], [later]))

    def kill_screen(self):
        subprocess.run(["tmux", "-S", str(self.stack / "claude" / "tty.sock"), "kill-server"], capture_output=True)

    def open_screen(self):
        """先非互動答一則（有 session id、tool.txt、ws.txt），再用 cli_session.open_cell 開畫面（同 aos-eca open -d）。"""
        self.say("先講一句")
        self.assertEqual(self.turn().returncode, 0)
        self.addCleanup(self.kill_screen)
        code = "import sys; sys.path.insert(0, %r); import cli_session; cli_session.open_cell(cli_session.Cell(%r))" % (
            str(CLI_SESSION.parent), str(self.stack / "claude"))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=self.env(), timeout=60,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_answer_waits_for_busy(self):
        """畫面開著、busy.txt 在（畫面上正在跑一輪）：yield＝退 0、信留 cur/；answer＝等 busy.txt 消失才貼進畫面答。"""
        self.open_screen()
        busy = self.stack / "claude" / "busy.txt"
        busy.write_text("x\n")
        sig = self.say("畫面忙完再說")
        n = len(self.history())
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.stage("cur"), len(self.history())), ([sig], n))     # 沒交出去：history 不動
        p = self.turn_bg(["--on-busy", "answer"])
        time.sleep(1.5)
        self.assertIsNone(p.poll())                                       # 還在等 busy.txt
        self.assertFalse((self.stack / "claude" / "turns.jsonl").exists())  # 還沒貼
        busy.unlink()
        out, err = p.communicate(timeout=60)
        self.assertEqual(p.returncode, 0, err)
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": "fake live: 畫面忙完再說"})
        self.assertEqual(self.stage("cur"), [])

    @unittest.skipUnless(HAS_TMUX, "沒有 tmux")
    def test_answer_with_client_attached(self):
        """有人接在畫面上（tmux client，pty 模擬）：yield＝退 0、信留 cur/；answer＝照樣貼進畫面答。"""
        self.open_screen()
        sock = str(self.stack / "claude" / "tty.sock")
        pid, fd = pty.fork()
        if pid == 0:
            os.execve("/usr/bin/env", ["env", "tmux", "-S", sock, "attach", "-t", "cli"], self.env(dict(TERM="xterm")))

        def drain():
            while select.select([fd], [], [], 0)[0]:
                try:
                    os.read(fd, 65536)
                except OSError:
                    return

        def reap():
            self.kill_screen()
            drain()
            os.waitpid(pid, 0)
            os.close(fd)
        self.addCleanup(reap)

        def attached():
            drain()
            r = subprocess.run(["tmux", "-S", sock, "list-clients", "-t", "cli"], capture_output=True, text=True)
            return bool(r.stdout.strip())
        self.assertTrue(self.until(attached))
        sig = self.say("有人看著也答")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.stage("cur"), [sig])
        p = self.turn_bg(["--on-busy", "answer"])
        self.assertTrue(self.until(lambda: (drain(), p.poll() is not None)[1], 60))
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertEqual(self.history()[-1], {"role": "assistant", "content": "fake live: 有人看著也答"})
        self.assertEqual(self.stage("cur"), [])

    # ------------------------------------------------------------ 工具形（--one）

    def test_one(self):
        """--one：stdin {"prompt"} → stdout 回答；對話在 $AOS_STACK 這格本身（同 lib/agent/claude）；錯照 lib 契約、開頭是定義資料夾名。"""
        cell = self.stack / "act" / "eca-claude"
        extra = dict(AOS_STACK=str(cell) + "/")
        r = self.turn(extra=extra, flags=["--one"], input=json.dumps({"prompt": "問一句"}))
        self.assertEqual(r.returncode, 0, r.stderr)
        sid = (cell / "session.txt").read_text().strip()
        self.assertEqual(r.stdout, "fake claude[%s]: 問一句\n" % sid[:8])
        self.assertTrue((cell / "transcripts" / ("claude-%s.jsonl" % sid)).is_symlink())
        self.assertFalse((self.stack / "history.jsonl").exists())            # 工具形不碰 queue／history
        r = self.turn(extra=extra, flags=["--one"], input=json.dumps({"text": "沒有 prompt"}))
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("eca-claude: ArgumentsBad "), r.stderr)
        self.assertEqual(r.stdout.strip(), r.stderr.strip())

    def test_one_on_busy(self):
        """--one 也認 --on-busy：lock 被拿著時 yield（預設）＝SessionBad 退 1；answer＝等放開後照常答。"""
        cell = self.stack / "act" / "eca-claude"
        cell.mkdir(parents=True)
        held = open(cell / "lock", "w")
        fcntl.flock(held, fcntl.LOCK_EX)
        extra = dict(AOS_STACK=str(cell) + "/")
        r = self.turn(extra=extra, flags=["--one"], input=json.dumps({"prompt": "忙"}))
        self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["eca-claude:", "SessionBad"]))
        p = subprocess.Popen(self.argv("claude", ["--one", "--on-busy", "answer"]), stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env(extra))
        self.addCleanup(lambda: p.poll() is None and p.kill())
        p.stdin.write(json.dumps({"prompt": "等一下"}))
        p.stdin.close()
        time.sleep(1)
        self.assertIsNone(p.poll())
        held.close()
        p.wait(timeout=60)                                   # stdin 上面已經關了：不用 communicate（它會再 flush 關掉的 stdin，11-03 修）
        out, err = p.stdout.read(), p.stderr.read()
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.endswith(": 等一下\n"), out)


if __name__ == "__main__":
    unittest.main()
