"""test_human - 給人用的 aos-say／aos-listen／aos-chat（proto8/extras/human，2026-10-24）：對 agent-nia 那種走 queue 的 agent 用假腦問答。

10-30 起照 agent 對話協議（CONVENTION P-42；thinking 2026-10-30-agent-lifecycle A-7、A-8、第 4 步）：say＝aos-post send --ordered
<stack>/queue、listen 只看 stack（信還在 queue 就等、不見了就印 history 最新的回答）。
11-03 拿掉 aos-listen 的 --status／--trace／LetterUnclaimed、aos-chat 的 --trace／/trace／/status（trace.jsonl 整個拿掉，thinking 2026-11-03-trace）：
原本看快照的案例改看 stack 的 state.json 與 aos_human.runners（listen 提醒「沒人在跑」用的同一個判法）。
agent＝demo/agent-nia 的格（註冊檔改成絕對路徑放在暫存資料夾，腦壞＝endpoint 換 openai 指到 dead_brain.DEAD）。
10-30 eca 第 7 步（去 hub 化）：External 段＝外部 coding agent（aos-loop 包 bin/aos-eca-turn、假 claude）跑著時 say／listen 照用、
runners 只靠 /proc 認得服務者（直接跑、掛 daemon 經 .stack symlink 兩種）；stack 的 server.txt 那招刪了。
設計：proto8/thinking/2026-10-24-say-listen.md。不連網。"""
import json, os, re, subprocess, tempfile, time, unittest
from pathlib import Path

from aos_bins import ROOT, path_with  # noqa: E402
from round_common import absolute  # noqa: E402

HUMAN = ROOT / "extras" / "human" / "bin"
SAY, LISTEN, CHAT = (str(HUMAN / n) for n in ("aos-say", "aos-listen", "aos-chat"))
NIA = ROOT / "demo" / "agent-nia"
DAN = str(ROOT / "demo" / "agent-eve")              # 舊協議（讀工作區 new/、不收 queue）：10-30 晚真腦實測發現 2；11-02 晚 agent-dan 刪除，改用它的複本 agent-eve
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")
from dead_brain import DEAD  # noqa: E402  （腦壞了＝連上去馬上被拒的網址）
SIG = re.compile(r"^\d{12}\.\d{20}\.\d+\.\d+$")
TURN = ROOT / "bin" / "aos-eca-turn"                # 10-30 eca：外部 coding agent 的一輪（External 段；10-31 前是 lib/eca/turn 格）
from test_fay import FAKE_CLAUDE, SYS_PATH  # noqa: E402  假 claude（不花額度）


def env(**kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(str(ROOT / "bin") + os.pathsep + e.get("PATH", ""))
    e.update(kw)
    return e


def run(*args, cwd=None, input=None, timeout=60, **kw):
    return subprocess.run(args, capture_output=True, text=True, env=env(**kw), cwd=cwd, input=input, timeout=timeout)


def runners(ws):
    """誰在跑這個工作區的 agent（aos_human.runners，listen 提醒「沒人在跑」用的同一套；11-03 起取代 --status 那行）：[(pid, 程式名)]。"""
    import sys
    sys.path.insert(0, str(HUMAN))
    import aos_human
    return aos_human.runners(aos_human.Where(str(ws), None))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        t = Path(self._tmp.name)
        self.ws = t / "ws"
        self.ws.mkdir()
        self.stack = self.ws / ".stack"
        self.agent = self.nia(t / "nia")

    def nia(self, where, brain=None, idle=False):
        """agent-nia 的一份拷貝：註冊檔改成絕對路徑；brain＝openai 的網址（腦壞用）；idle＝loop.json 改指 fsm-idle.json＋常駐的 loop。"""
        where.mkdir()
        for f in ("_entry", "system.txt"):
            (where / f).write_bytes((NIA / f).read_bytes())
        loop = json.loads((NIA / "loop.json").read_text())
        loop["exec"]["cwd"] = os.path.normpath(os.path.join(NIA, loop["exec"]["cwd"]))   # lib/agent/round
        parts = json.loads((NIA / "parts.json").read_text())
        tools = json.loads((NIA / "tools.json").read_text())
        parts = absolute(parts, NIA)
        for row in tools["tools"].values():
            row["path"] = os.path.normpath(os.path.join(NIA, row["path"]))
        if brain:
            parts["endpoint"]["default"] = {".env": {"AOS_BRAIN_URL": brain, "AOS_BRAIN_MODEL": "m"},
                                            "_entry": str(ROOT / "lib" / "endpoint" / "openai")}
        if idle:
            loop["exec"]["argv"] = ["aos-fsm", "fsm-idle.json"]
            del loop["max"]
            loop["interval_ms"] = 100
        (where / "loop.json").write_text(json.dumps(loop))
        (where / "parts.json").write_text(json.dumps(parts))
        (where / "tools.json").write_text(json.dumps(tools))
        return str(where)

    def say(self, *words, **kw):
        r = run(SAY, "--ws", str(self.ws), *words, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def go(self, agent=None, **kw):
        return run("aos-exec", "--ws", str(self.ws), agent or self.agent, **kw)

    def queue(self, stage):
        d = self.stack / "queue" / stage
        return sorted(os.listdir(d)) if d.is_dir() else []

    def history(self):
        p = self.stack / "history.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


class SayTest(Base):
    def test_say_sends_one_ordered_letter(self):
        sig = self.say("現在", "幾點")
        self.assertRegex(sig, SIG)
        self.assertTrue(sig.startswith("000000000001."))
        self.assertEqual(self.queue("new"), [sig])
        letter = json.loads((self.stack / "queue" / "new" / sig / "letter.json").read_text())
        self.assertEqual(letter["body"], {"role": "user", "content": "現在 幾點"})
        self.assertEqual(sorted(os.listdir(self.ws)), [".stack"])        # 工作區不長 new/、暫存檔

    def test_stdin_cwd_and_stack_flag(self):
        r = run(SAY, cwd=str(self.ws), input="第一行\n第二行\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = json.loads((self.stack / "queue" / "new" / r.stdout.strip() / "letter.json").read_text())["body"]
        self.assertEqual(body["content"], "第一行\n第二行")              # 結尾換行去掉
        self.assertIn("目前沒有程式在跑這隻 agent", r.stderr)            # 沒人跑：提醒、不算錯
        other = self.ws / "elsewhere"
        r = run(SAY, "--ws", str(self.ws), "--stack", str(other), "到別的 stack")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(other / "queue" / "new"), [r.stdout.strip()])
        r = run(SAY, "--ws", str(self.ws), "環境變數的 stack", AOS_STACK=str(other))
        self.assertEqual(len(os.listdir(other / "queue" / "new")), 2)

    def test_order(self):
        sigs = [self.say("q%d" % i) for i in range(5)]
        self.assertEqual(sigs, sorted(sigs))
        self.assertEqual([s[:12] for s in sigs], ["%012d" % i for i in range(1, 6)])

    def test_errors(self):
        r = run(SAY, "--ws", str(self.ws / "nope"), "x")
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "WsMissing"))
        r = run(SAY, "--ws", str(self.ws), input="  \n")
        self.assertRegex(r.stderr, r"^aos-say: ArgumentsBad usage: ")
        r = run(SAY, "--bogus", "x")
        self.assertRegex(r.stderr, r"^aos-say: FlagUnknown usage: ")
        r = run(SAY, "--ws", str(self.ws), "--name", "q1.txt", "x")       # --name 拿掉了（信號由 aos-post 給）
        self.assertRegex(r.stderr, r"^aos-say: FlagUnknown usage: ")


class ListenTest(Base):
    def test_answer_already_there(self):
        """答案先到、再 listen：不漏（信不見了＝印 history 最新的回答）。"""
        sig = self.say("現在幾點")
        r = self.go()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.queue("new") + self.queue("cur"), [])
        r = run(LISTEN, "--ws", str(self.ws))                    # 不帶信號：new/ cur/ 空＝印最新那則回答
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 現在幾點（clock said:"), r.stdout)
        self.assertEqual(r.stdout.count("\n"), 1)

    def test_waits_while_agent_runs_later(self):
        sig = self.say("等我")
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--timeout", "30"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(1.5)                                       # listen 先開：這時沒人在跑，會提醒一次
        self.assertEqual(self.go().returncode, 0)
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.startswith("FAKE ANSWER to: 等我"), out)
        self.assertIn("還在 queue 的 new/，但目前沒有程式在跑", err)

    def test_old_protocol_agent_waits(self):
        """say 之後拿舊協議的 agent（agent-eve；11-02 晚前是 agent-dan）跑：退 0、信原封留在 new/；listen 照等到逾時（11-03 起沒有
        LetterUnclaimed：那是靠 trace.jsonl 的時間判的）；之後換走 queue 的 agent 跑就答得出。"""
        sig = self.say("舊協議")
        self.assertEqual(self.go(DAN).returncode, 0)
        self.assertEqual(self.queue("new"), [sig])
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "1")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr.splitlines()[-1], r"^aos-listen: AnswerMissing 等了 1 秒")
        self.assertIn("還在 queue 的 new/，但目前沒有程式在跑", r.stderr)
        self.assertEqual(self.go().returncode, 0)                # 換走 queue 的 agent-nia：答得出
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "5")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_waits_while_letter_in_cur(self):
        """信在 cur/（認領了、腦壞停住）：listen 照等、說信在 cur/ 沒人在跑；修好再跑就答出。"""
        sig = self.say("壞腦")
        bad = self.nia(Path(self._tmp.name) / "bad", brain=DEAD)
        r = self.go(bad)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.queue("cur"), [sig])
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("在 queue 的 cur/（認領了、還沒答完），但目前沒有程式在跑", r.stderr)
        self.assertRegex(r.stderr.splitlines()[-1], r"^aos-listen: AnswerMissing 等了 1 秒.*（信在 queue 的 cur/）")
        self.assertFalse((self.stack / "trace.jsonl").exists())               # 11-03：fsm 不寫 trace
        self.assertEqual(json.loads((self.stack / "state.json").read_text())["phase"], "done")   # aos-loop 的 state 窗（失敗也是 done）
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--timeout", "30"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(0.5)
        self.assertEqual(self.go().returncode, 0)                        # 換回假腦：接著做同一封
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.startswith("FAKE ANSWER to: 壞腦"), out)

    def test_paused_letter_waits(self):
        """常駐（idle）的 aos-loop 被 ctl 暫停：state.json 的 phase paused、runners 認得有人在跑；寄的信留在 new/。"""
        agent = self.nia(Path(self._tmp.name) / "idle", idle=True)
        self.stack.mkdir()
        (self.stack / "ctl.json").write_text('{"paused": true}')
        p = subprocess.Popen(["aos-exec", "--ws", str(self.ws), agent], stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, text=True, env=env())
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.communicate()))
        end = time.time() + 20
        while time.time() < end:
            st = self.stack / "state.json"
            if st.exists() and json.loads(st.read_text() or "{}").get("phase") == "paused":
                break
            time.sleep(0.05)
        sig = self.say("暫停中")
        self.assertIn("aos-loop", [n for _, n in runners(self.ws)])
        self.assertEqual(self.queue("new"), [sig])
        (self.stack / "ctl.json").write_text('{"paused": false}')
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "20")
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 暫停中"), r.stdout + r.stderr)
        (self.stack / "ctl.json").write_text('{"stopped": true}')
        self.assertEqual(p.wait(timeout=20), 0)

    def test_unknown_and_usage(self):
        r = run(LISTEN, "--ws", str(self.ws))                           # 沒寄過、也沒回答
        self.assertRegex(r.stderr, r"^aos-listen: QuestionUnknown ")
        r = run(LISTEN, "--ws", str(self.ws), "000000000001.nope")     # 11-01 晚翻案：信號參數拿掉
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: .*不收位置參數")
        r = run(LISTEN, "--ws", str(self.ws), "--last", "2", "x")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "abc")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "1", "--follow")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")
        for gone in ("--status", "--trace"):                            # 11-03 拿掉
            r = run(LISTEN, "--ws", str(self.ws), gone)
            self.assertRegex(r.stderr, r"^aos-listen: FlagUnknown ")

    def test_waits_for_latest_letter(self):
        """aos-say 話 && aos-listen：連寄兩封，listen 等的是最新那封；答完印最新的回答。"""
        self.say("第一封")
        self.say("第二封")
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--timeout", "30"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(0.5)
        self.assertEqual(self.go().returncode, 0)
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.startswith("FAKE ANSWER to: 第二封"), out)

    def test_last_prints_question_and_answer(self):
        self.say("一")
        self.say("二")
        self.assertEqual(self.go().returncode, 0)
        r = run(LISTEN, "--ws", str(self.ws), "--last", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"(?s)^== #1\n> 一\nFAKE ANSWER to: 一.*\n== #2\n> 二\nFAKE ANSWER to: 二")
        r = run(LISTEN, "--ws", str(self.ws), "--last", "1")
        self.assertTrue(r.stdout.startswith("== #2\n> 二\n"), r.stdout)

    def test_follow_prints_new_answers(self):
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--follow"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=env())
        time.sleep(0.5)
        self.say("跟著看")
        self.assertEqual(self.go().returncode, 0)
        time.sleep(1)
        p.terminate()
        out, _ = p.communicate(timeout=10)
        self.assertIn("== #1\n> 跟著看\nFAKE ANSWER to: 跟著看", out)



class ChatTest(Base):
    def test_two_questions_keep_history(self):
        r = run(CHAT, "--ws", str(self.ws), self.agent, input="你好\n/status\n第二句\n//斜線開頭\n/bogus\n")   # /status 11-03 拿掉＝沒有這個指令
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 3, r.stdout)              # stdout 只有三個回答
        self.assertTrue(lines[0].startswith("FAKE ANSWER to: 你好"))
        self.assertTrue(lines[1].startswith("FAKE ANSWER to: 第二句"))
        self.assertTrue(lines[2].startswith("FAKE ANSWER to: /斜線開頭"))
        self.assertEqual(r.stderr.count("沒有這個指令"), 2)       # /status、/bogus
        self.assertEqual([m["content"] for m in self.history() if m["role"] == "user"], ["你好", "第二句", "/斜線開頭"])
        self.assertEqual(self.queue("new") + self.queue("cur"), [])

    def test_agent_fails_then_run_resumes(self):
        bad = self.nia(Path(self._tmp.name) / "bad", brain=DEAD)
        r = run(CHAT, "--ws", str(self.ws), bad, input="壞腦那題\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIn("endpoint: BrainFailed", r.stderr)       # agent 的錯誤一行原樣看得到
        self.assertIn("agent 停了（agent 結束碼 1）", r.stderr)
        self.assertIn("queue 裡還有 1 封沒答", r.stderr)
        r = run(CHAT, "--ws", str(self.ws), self.agent, input="/run\n")   # 新開一個 chat（假腦）：認得還沒答的那封，/run 接著做
        self.assertIn("queue 裡已經有 1 封還沒答", r.stderr)
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 壞腦那題"), r.stdout + r.stderr)

    def test_old_protocol_agent_hint(self):
        """chat 替你跑舊協議的 agent：跑完信還在 new/，提醒可能是舊協議（10-30 晚真腦實測發現 2）。"""
        r = run(CHAT, "--ws", str(self.ws), DAN, input="你好\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
        self.assertIn("agent 跑完了，但 queue 裡還有 1 封沒答", r.stderr)
        self.assertIn("舊協議", r.stderr)

    def test_without_agent_waits_for_other_runner(self):
        p = subprocess.Popen([CHAT, "--ws", str(self.ws)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env())
        p.stdin.write("別人跑\n")
        p.stdin.flush()
        deadline = time.time() + 10
        while not self.queue("new"):
            self.assertLess(time.time(), deadline)
            time.sleep(0.1)
        time.sleep(1.5)
        self.assertEqual(self.go().returncode, 0)
        out, err = p.communicate("", timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.startswith("FAKE ANSWER to: 別人跑"), out + err)
        self.assertIn("目前沒有程式在跑這隻 agent", err)

    def test_agent_missing(self):
        r = run(CHAT, "--ws", str(self.ws), str(self.ws / "nope"), input="")
        self.assertRegex(r.stderr, r"^aos-chat: AgentMissing ")
        r = run(CHAT, "--ws", str(self.ws), "--trace", input="")      # 11-03 拿掉
        self.assertRegex(r.stderr, r"^aos-chat: FlagUnknown ")


class External(Base):
    """10-30 eca 第 7 步（C 結論 9、F 結論 18；衝突 6 刪 server.txt）：外部 coding agent＝aos-loop 包著 aos-eca-turn 的定義（P-43 草稿），
    say／listen 不用改；服務者（aos_human.runners）只靠 /proc。定義在這裡臨時組（demo/eca-claude 還沒有），CLI 用 test_fay 的假 claude。"""

    def setUp(self):
        super().setUp()
        t = Path(self._tmp.name)
        self.bin = t / "fakebin"
        self.bin.mkdir()
        (self.bin / "claude").write_text(FAKE_CLAUDE)
        (self.bin / "claude").chmod(0o755)
        self.eca = t / "eca-claude"                     # 定義：cli.json＋loop.json（叫 aos-eca-turn）＋_entry 轉 aos-loop
        self.eca.mkdir()
        cfg = json.loads((ROOT / "lib" / "agent" / "claude" / "cli.json").read_text())
        (self.eca / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
        (self.eca / "loop.json").write_text(json.dumps({"exec": [str(TURN), "--on-empty", "idle", str(self.eca)], "interval_ms": 100,
                                                        "ctl": "ctl.json", "state": "state.json"}))
        (self.eca / "_entry").write_text(json.dumps(["aos-loop", "loop.json"]))
        self.xenv = dict(PATH=path_with(str(self.bin) + os.pathsep + str(ROOT / "bin") + os.pathsep + SYS_PATH),
                         FAKE_LOG=str(t / "cli.log"), CLAUDE_CONFIG_DIR=str(t / "claude-home"))

    def xrun(self, *args, **kw):
        return run(*args, **dict(self.xenv, **kw))

    def popen(self, argv, **kw):
        e = env(**dict(self.xenv, **kw))
        for k in ("TMUX", "CODEX_HOME", "FAKE_TRANSCRIPTS"):
            e.pop(k, None)
        p = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=e)
        self.addCleanup(lambda: (p.poll() is None and p.kill(), p.communicate()))
        return p

    def phase(self, stack, want):
        end = time.time() + 20
        while time.time() < end:
            try:
                if json.loads((stack / "state.json").read_text() or "{}").get("phase") in want:
                    return True
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        return False

    def test_external_runner_and_phase(self):
        """aos-exec 直接跑外部範本（idle）：say／listen 答得出；runners 認得服務者（aos-loop）；暫停時 phase paused；
        stack 裡沒有 server.txt、trace.jsonl（11-03）。"""
        p = self.popen(["aos-exec", "--ws", str(self.ws), str(self.eca)])
        self.assertTrue(self.phase(self.stack, ("waiting", "running")))
        sig = self.say("你好", **self.xenv)
        r = self.xrun(LISTEN, "--ws", str(self.ws), "--timeout", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("fake claude[") and r.stdout.rstrip().endswith(": 你好"), r.stdout)
        self.assertIn((p.pid, "aos-loop"), runners(self.ws))
        self.assertFalse((self.stack / "server.txt").exists())
        self.assertFalse((self.stack / "trace.jsonl").exists())
        (self.stack / "ctl.json").write_text('{"paused": true}')
        self.assertTrue(self.phase(self.stack, ("paused",)))
        self.assertIn("aos-loop", [n for _, n in runners(self.ws)])
        (self.stack / "ctl.json").write_text('{"stopped": true}')
        self.assertEqual(p.wait(timeout=20), 0)
        self.assertEqual(runners(self.ws), [])

    def test_status_sees_runner_under_daemon(self):
        """掛在 daemon 底下（aos-daemon-ctl add --ws）：子 loop 的 AOS_STACK 是 daemon 的小格、工作區的 .stack 是指過去的 symlink，
        runners 照樣認得服務者；say／listen 經 symlink 答得出。"""
        ds = Path(self._tmp.name) / "dstack"
        ds.mkdir()
        dj = Path(self._tmp.name) / "daemon.json"
        dj.write_text(json.dumps({"interval_ms": 100, "ctl": "ctl.json", "state": "state.json",
                                  "loops_ctl_mailbox": "loops_ctl_mailbox"}))
        d = self.popen(["aos-daemon", str(dj)], AOS_STACK=str(ds))
        end = time.time() + 20
        while not (ds / "loops_ctl_mailbox" / "new").is_dir():
            self.assertLess(time.time(), end)
            time.sleep(0.05)
        r = self.xrun(str(ROOT / "bin" / "aos-daemon-ctl"), "--daemon-stack", str(ds), "add", "--ws", str(self.ws), "--name", "bob",
                      str(self.eca))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(os.readlink(self.stack), str(ds / "loops" / "bob"))
        self.assertTrue(self.phase(ds / "loops" / "bob", ("waiting", "running")))
        sig = self.say("在 daemon 底下", **self.xenv)
        r = self.xrun(LISTEN, "--ws", str(self.ws), "--timeout", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.rstrip().endswith(": 在 daemon 底下"), r.stdout)
        self.assertIn("aos-loop", [n for _, n in runners(self.ws)])
        self.assertTrue(self.phase(self.stack, ("waiting", "running")))
        (ds / "ctl.json").write_text('{"stopped": true}')
        self.assertEqual(d.wait(timeout=30), 0)


if __name__ == "__main__":
    unittest.main()
