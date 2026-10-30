"""test_human - 給人用的 aos-say／aos-listen／aos-chat（proto8/extras/human，2026-10-24）：對 agent-nia 那種走 queue 的 agent 用假腦問答。

10-30 起照 agent 對話協議（CONVENTION P-42；thinking 2026-10-30-agent-lifecycle A-7、A-8、第 4 步）：say＝aos-post send --ordered
<stack>/queue、listen 只看 stack（信還在 queue 就等、不見了就印 history 最新的回答；--status 看 aos-loop state.json 的 phase）。
agent＝demo/agent-nia 的格（註冊檔改成絕對路徑放在暫存資料夾，腦壞＝endpoint 換 openai 指到 dead_brain.DEAD）。
10-30 eca 第 7 步（去 hub 化）：External 段＝外部 coding agent（aos-loop 包 lib/eca/turn、假 claude）跑著時 say／listen 照用、
--status 只靠 /proc 認得服務者（直接跑、掛 daemon 經 .stack symlink 兩種）；stack 的 server.txt 那招刪了。
設計：proto8/thinking/2026-10-24-say-listen.md。不連網。"""
import json, os, re, subprocess, tempfile, time, unittest
from pathlib import Path

from aos_bins import ROOT, path_with  # noqa: E402

HUMAN = ROOT / "extras" / "human" / "bin"
SAY, LISTEN, CHAT = (str(HUMAN / n) for n in ("aos-say", "aos-listen", "aos-chat"))
NIA = ROOT / "demo" / "agent-nia"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "ROUND_ON_EMPTY")
from dead_brain import DEAD  # noqa: E402  （腦壞了＝連上去馬上被拒的網址）
SIG = re.compile(r"^\d{12}\.\d{20}\.\d+\.\d+$")
TURN = ROOT / "lib" / "eca" / "turn"                 # 10-30 eca：外部 coding agent 的一格（External 段）
from test_fay import FAKE_CLAUDE, SYS_PATH  # noqa: E402  假 claude（不花額度）


def env(**kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(str(ROOT / "bin") + os.pathsep + e.get("PATH", ""))
    e.update(kw)
    return e


def run(*args, cwd=None, input=None, timeout=60, **kw):
    return subprocess.run(args, capture_output=True, text=True, env=env(**kw), cwd=cwd, input=input, timeout=timeout)


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
        """agent-nia 的一份拷貝：註冊檔改成絕對路徑；brain＝openai 的網址（腦壞用）；idle＝ROUND_ON_EMPTY idle＋常駐的 loop。"""
        where.mkdir()
        for f in ("_entry", "system.txt"):
            (where / f).write_bytes((NIA / f).read_bytes())
        loop = json.loads((NIA / "loop.json").read_text())
        parts = json.loads((NIA / "parts.json").read_text())
        tools = json.loads((NIA / "tools.json").read_text())
        for reg in (parts["parts"], tools["tools"]):
            for row in reg.values():
                row["path"] = os.path.normpath(os.path.join(NIA, row["path"]))
        if brain:
            parts["parts"]["endpoint/default"] = {"path": str(ROOT / "lib" / "endpoint" / "openai"),
                                                  "env": {"AOS_BRAIN_URL": brain, "AOS_BRAIN_MODEL": "m"}}
        if idle:
            parts["parts"]["round"]["env"] = {"ROUND_ON_EMPTY": "idle"}
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
        r = run(LISTEN, "--ws", str(self.ws), sig)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 現在幾點（clock said:"), r.stdout)
        self.assertEqual(r.stdout.count("\n"), 1)

    def test_waits_while_agent_runs_later(self):
        sig = self.say("等我")
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--trace", "--timeout", "30", sig],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(1.5)                                       # listen 先開：這時沒人在跑，會提醒一次
        self.assertEqual(self.go().returncode, 0)
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.startswith("FAKE ANSWER to: 等我"), out)
        self.assertIn("還在 queue 的 new/，但目前沒有程式在跑", err)
        self.assertIn("[叫工具 clock {}]", err)                # --trace：工具呼叫與每格一行
        self.assertRegex(err, r"· queue claim \d+ms")

    def test_waits_while_letter_in_cur(self):
        """信在 cur/（認領了、腦壞停住）：listen 照等、說停在哪一格；修好再跑就答出。"""
        sig = self.say("壞腦")
        bad = self.nia(Path(self._tmp.name) / "bad", brain=DEAD)
        r = self.go(bad)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.queue("cur"), [sig])
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "1", sig)
        self.assertEqual(r.returncode, 1)
        self.assertIn("做到一半停了：上次停在 endpoint/default 那格、結束碼 1", r.stderr)
        self.assertRegex(r.stderr.splitlines()[-1], r"^aos-listen: AnswerMissing 等了 1 秒.*（信在 queue 的 cur/）")
        r = run(LISTEN, "--ws", str(self.ws), "--status")
        self.assertIn("queue    new 0、cur 1、done 0", r.stdout)
        self.assertIn("最後一格 endpoint/default 退 1", r.stdout)
        self.assertIn("← 卡住了", r.stdout)
        self.assertIn("loop     phase done", r.stdout)                 # aos-loop 的 state 窗（失敗也是 done、帶 code）
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--timeout", "30", sig], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(0.5)
        self.assertEqual(self.go().returncode, 0)                        # 換回假腦：接著做同一封
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.startswith("FAKE ANSWER to: 壞腦"), out)

    def test_status_shows_paused(self):
        """常駐（idle）的 aos-loop 被 ctl 暫停：--status 看得到 phase paused、有人在跑；寄的信留在 new/。"""
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
        r = run(LISTEN, "--ws", str(self.ws), "--status")
        self.assertIn("loop     phase paused", r.stdout)
        self.assertRegex(r.stdout, r"在跑     .*aos-loop")
        self.assertIn("queue    new 1、cur 0、done 0", r.stdout)
        self.assertEqual(self.queue("new"), [sig])
        (self.stack / "ctl.json").write_text('{"paused": false}')
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "20", sig)
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 暫停中"), r.stdout + r.stderr)
        (self.stack / "ctl.json").write_text('{"stopped": true}')
        self.assertEqual(p.wait(timeout=20), 0)

    def test_unknown_and_usage(self):
        r = run(LISTEN, "--ws", str(self.ws), "000000000001.nope")
        self.assertRegex(r.stderr, r"^aos-listen: QuestionUnknown ")
        r = run(LISTEN, "--ws", str(self.ws), "--last", "2", "x")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "abc", "x")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")

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
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=env())
        time.sleep(0.5)
        self.say("跟著看")
        self.assertEqual(self.go().returncode, 0)
        time.sleep(1)
        p.terminate()
        out, _ = p.communicate(timeout=10)
        self.assertIn("== #1\n> 跟著看\nFAKE ANSWER to: 跟著看", out)


class TailNewlineTest(Base):
    def test_tool_result_newlines_not_literal(self):
        import sys
        sys.path.insert(0, str(HUMAN))
        import aos_human as h
        w = h.Where(str(self.ws), None)
        Path(w.stack).mkdir(parents=True, exist_ok=True)
        t = h.Tail(w)
        with open(Path(w.stack) / "history.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"role": "tool", "tool_call_id": "x", "content": "391\n"}) + "\n")
            f.write(json.dumps({"role": "tool", "tool_call_id": "y", "content": "a\nb\n"}) + "\n")
        self.assertEqual(t.lines(), ["[工具 回 391]", "[工具 回 a ⏎ b]"])


class ChatTest(Base):
    def test_two_questions_keep_history(self):
        r = run(CHAT, "--ws", str(self.ws), self.agent, input="你好\n/status\n第二句\n//斜線開頭\n/bogus\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 3, r.stdout)              # stdout 只有三個回答
        self.assertTrue(lines[0].startswith("FAKE ANSWER to: 你好"))
        self.assertTrue(lines[1].startswith("FAKE ANSWER to: 第二句"))
        self.assertTrue(lines[2].startswith("FAKE ANSWER to: /斜線開頭"))
        self.assertIn("沒有這個指令", r.stderr)
        self.assertIn("loop     phase done", r.stderr)          # /status 印在 stderr
        self.assertEqual([m["content"] for m in self.history() if m["role"] == "user"], ["你好", "第二句", "/斜線開頭"])
        self.assertEqual(self.queue("new") + self.queue("cur"), [])

    def test_agent_fails_then_run_resumes(self):
        bad = self.nia(Path(self._tmp.name) / "bad", brain=DEAD)
        r = run(CHAT, "--ws", str(self.ws), bad, input="壞腦那題\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIn("endpoint: BrainFailed", r.stderr)       # agent 的錯誤一行原樣看得到
        self.assertIn("agent 停了（停在 endpoint/default 那格、結束碼 1、agent 結束碼 1）", r.stderr)
        self.assertIn("queue 裡還有 1 封沒答", r.stderr)
        r = run(CHAT, "--ws", str(self.ws), self.agent, input="/run\n")   # 新開一個 chat（假腦）：認得還沒答的那封，/run 接著做
        self.assertIn("queue 裡已經有 1 封還沒答", r.stderr)
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 壞腦那題"), r.stdout + r.stderr)

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


class External(Base):
    """10-30 eca 第 7 步（C 結論 9、F 結論 18；衝突 6 刪 server.txt）：外部 coding agent＝aos-loop 包著 lib/eca/turn 的定義（P-43 草稿），
    say／listen 不用改；--status 的服務者只靠 /proc。定義在這裡臨時組（demo/eca-claude 還沒有），CLI 用 test_fay 的假 claude。"""

    def setUp(self):
        super().setUp()
        t = Path(self._tmp.name)
        self.bin = t / "fakebin"
        self.bin.mkdir()
        (self.bin / "claude").write_text(FAKE_CLAUDE)
        (self.bin / "claude").chmod(0o755)
        self.eca = t / "eca-claude"                     # 定義：cli.json＋loop.json（一格 turn）＋_entry 轉 aos-loop
        self.eca.mkdir()
        cfg = json.loads((ROOT / "lib" / "agent" / "claude" / "cli.json").read_text())
        (self.eca / "cli.json").write_text(json.dumps(dict(cfg, timeout_ms=15000)))
        (self.eca / "loop.json").write_text(json.dumps({"exec": [str(TURN), str(self.eca)], "interval_ms": 100,
                                                        "ctl": "ctl.json", "state": "state.json"}))
        (self.eca / "_entry").write_text(json.dumps(["aos-loop", "loop.json"]))
        self.xenv = dict(PATH=path_with(str(self.bin) + os.pathsep + str(ROOT / "bin") + os.pathsep + SYS_PATH),
                         FAKE_LOG=str(t / "cli.log"), CLAUDE_CONFIG_DIR=str(t / "claude-home"), ECA_ON_EMPTY="idle")

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

    def test_status_shows_external_runner_and_phase(self):
        """aos-exec 直接跑外部範本（idle）：say／listen 答得出；--status 印得出服務者（aos-loop）、phase、最後一格 turn；
        暫停時 phase paused；stack 裡沒有 server.txt。"""
        p = self.popen(["aos-exec", "--ws", str(self.ws), str(self.eca)])
        self.assertTrue(self.phase(self.stack, ("waiting", "running")))
        sig = self.say("你好", **self.xenv)
        r = self.xrun(LISTEN, "--ws", str(self.ws), "--timeout", "30", sig)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("fake claude[") and r.stdout.rstrip().endswith(": 你好"), r.stdout)
        r = self.xrun(LISTEN, "--ws", str(self.ws), "--status")
        self.assertRegex(r.stdout, r"在跑     .*aos-loop（pid %d）" % p.pid)
        self.assertRegex(r.stdout, r"loop     phase (waiting|running)（state\.json）")
        self.assertRegex(r.stdout, r"最後一格 turn 退 0")
        self.assertFalse((self.stack / "server.txt").exists())
        (self.stack / "ctl.json").write_text('{"paused": true}')
        self.assertTrue(self.phase(self.stack, ("paused",)))
        r = self.xrun(LISTEN, "--ws", str(self.ws), "--status")
        self.assertIn("loop     phase paused", r.stdout)
        self.assertRegex(r.stdout, r"在跑     .*aos-loop")
        (self.stack / "ctl.json").write_text('{"stopped": true}')
        self.assertEqual(p.wait(timeout=20), 0)
        r = self.xrun(LISTEN, "--ws", str(self.ws), "--status")
        self.assertIn("在跑     沒有", r.stdout)

    def test_status_sees_runner_under_daemon(self):
        """掛在 daemon 底下（aos-daemon-ctl add --ws）：子 loop 的 AOS_STACK 是 daemon 的小格、工作區的 .stack 是指過去的 symlink，
        --status 照樣認得服務者；say／listen 經 symlink 答得出。"""
        ds = Path(self._tmp.name) / "dstack"
        ds.mkdir()
        dj = Path(self._tmp.name) / "daemon.json"
        dj.write_text(json.dumps({"interval_ms": 100, "ctl": "ctl.json", "state": "state.json", "loops_mailbox": "loops_mailbox"}))
        d = self.popen(["aos-daemon", str(dj)], AOS_STACK=str(ds))
        end = time.time() + 20
        while not (ds / "loops_mailbox" / "new").is_dir():
            self.assertLess(time.time(), end)
            time.sleep(0.05)
        r = self.xrun(str(ROOT / "bin" / "aos-daemon-ctl"), "--daemon", str(ds), "add", "--ws", str(self.ws), "--name", "bob",
                      str(self.eca))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(os.readlink(self.stack), str(ds / "bob"))
        self.assertTrue(self.phase(ds / "bob", ("waiting", "running")))
        sig = self.say("在 daemon 底下", **self.xenv)
        r = self.xrun(LISTEN, "--ws", str(self.ws), "--timeout", "30", sig)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.rstrip().endswith(": 在 daemon 底下"), r.stdout)
        r = self.xrun(LISTEN, "--ws", str(self.ws), "--status")
        self.assertRegex(r.stdout, r"在跑     .*aos-loop")
        self.assertRegex(r.stdout, r"loop     phase (waiting|running)")
        (ds / "ctl.json").write_text('{"stopped": true}')
        self.assertEqual(d.wait(timeout=30), 0)


if __name__ == "__main__":
    unittest.main()
