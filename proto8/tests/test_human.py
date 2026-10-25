"""test_human - 給人用的 aos-say／aos-listen／aos-chat（proto8/extras/human，2026-10-24）：對 demo/agent-dan 用假腦問答。

設計：proto8/thinking/2026-10-24-say-listen.md。不連網（假腦＝沒設 AOS_BRAIN_URL；腦壞＝指到連不上的埠）。"""
import os, re, subprocess, tempfile, time, unittest
from pathlib import Path

from aos_bins import ROOT, path_with  # noqa: E402

HUMAN = ROOT / "extras" / "human" / "bin"
SAY, LISTEN, CHAT = (str(HUMAN / n) for n in ("aos-say", "aos-listen", "aos-chat"))
DAN = str(ROOT / "demo" / "agent-dan")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")
DEAD = "http://127.0.0.1:9/v1"          # 沒人聽的埠：腦連不上
NAME = re.compile(r"^\d{8}T\d{6}\.\d{3}Z\.txt$")


def env(**kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(kw)
    return e


def run(*args, cwd=None, input=None, timeout=60, **kw):
    return subprocess.run(args, capture_output=True, text=True, env=env(**kw), cwd=cwd, input=input, timeout=timeout)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def say(self, *words, **kw):
        r = run(SAY, "--ws", str(self.ws), *words, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def dan(self, **kw):
        return run("aos-exec", "--ws", str(self.ws), DAN, **kw)


class SayTest(Base):
    def test_say_puts_one_file_in_new(self):
        name = self.say("現在", "幾點")
        self.assertRegex(name, NAME)
        self.assertEqual((self.ws / "new" / name).read_text(encoding="utf-8"), "現在 幾點\n")
        self.assertEqual(sorted(os.listdir(self.ws)), ["new"])          # 暫存檔沒留下
        self.assertEqual(os.listdir(self.ws / "new"), [name])

    def test_stdin_and_cwd_default(self):
        r = run(SAY, cwd=str(self.ws), input="第一行\n第二行\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.ws / "new" / r.stdout.strip()).read_text(encoding="utf-8"), "第一行\n第二行\n")
        self.assertIn("目前沒有程式在跑這個工作區", r.stderr)            # 沒人跑：提醒、不算錯

    def test_names_sort_in_order(self):
        names = [self.say("q%d" % i) for i in range(5)]
        self.assertEqual(names, sorted(names))
        self.assertEqual(len(set(names)), 5)

    def test_given_name_and_reuse(self):
        self.assertEqual(self.say("--name", "q1.txt", "你好"), "q1.txt")
        r = run(SAY, "--ws", str(self.ws), "--name", "q1.txt", "再一次")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^aos-say: NameBad .*q1\.txt 用過了（在 new/）")
        (self.ws / "out").mkdir()
        (self.ws / "out" / "q2.txt").write_text("舊答案\n")
        r = run(SAY, "--ws", str(self.ws), "--name", "q2.txt", "x")
        self.assertRegex(r.stderr, r"^aos-say: NameBad .*在 out/")
        r = run(SAY, "--ws", str(self.ws), "--name", "../x", "x")
        self.assertRegex(r.stderr, r"^aos-say: NameBad ")

    def test_errors(self):
        r = run(SAY, "--ws", str(self.ws / "nope"), "x")
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "WsMissing"))
        r = run(SAY, "--ws", str(self.ws), input="  \n")
        self.assertRegex(r.stderr, r"^aos-say: ArgumentsBad usage: ")
        r = run(SAY, "--bogus", "x")
        self.assertRegex(r.stderr, r"^aos-say: FlagUnknown usage: ")


class ListenTest(Base):
    def test_answer_already_there(self):
        name = self.say("現在幾點")
        r = self.dan()
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run(LISTEN, "--ws", str(self.ws), name)
        self.assertEqual((r.returncode, r.stdout), (0, (self.ws / "out" / name).read_text(encoding="utf-8")))
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 現在幾點"))

    def test_waits_while_agent_runs_later(self):
        name = self.say("等我")
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws), "--trace", "--timeout", "30", name],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env())
        time.sleep(1.5)                                       # listen 先開：這時沒人在跑，會提醒一次
        self.assertEqual(self.dan().returncode, 0)
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.startswith("FAKE ANSWER to: 等我"))
        self.assertIn("還在 new/，但目前沒有程式在跑", err)
        self.assertIn("[叫工具 clock {}]", err)                # --trace：工具呼叫與每格一行
        self.assertRegex(err, r"· think \d+ms")

    def test_stuck_hint_and_timeout(self):
        name = self.say("壞腦")
        r = self.dan(AOS_BRAIN_URL=DEAD)
        self.assertNotEqual(r.returncode, 0)
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "1", name)
        self.assertEqual(r.returncode, 1)
        self.assertIn("做到一半停了：上次停在 think 格、結束碼 1", r.stderr)
        self.assertRegex(r.stderr.splitlines()[-1], r"^aos-listen: AnswerMissing 等了 1 秒.*（題目在 cur/）")
        r = run(LISTEN, "--ws", str(self.ws), "--status")
        self.assertIn("狀態     think", r.stdout)
        self.assertIn("題目     new 0、cur 1、out 0、done 0", r.stdout)
        self.assertIn("← 卡住了", r.stdout)

    def test_unknown_and_usage(self):
        r = run(LISTEN, "--ws", str(self.ws), "nope.txt")
        self.assertRegex(r.stderr, r"^aos-listen: QuestionUnknown ")
        r = run(LISTEN, "--ws", str(self.ws), "--last", "2", "x.txt")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")
        r = run(LISTEN, "--ws", str(self.ws), "--timeout", "abc", "x.txt")
        self.assertRegex(r.stderr, r"^aos-listen: ArgumentsBad usage: ")

    def test_last_prints_question_and_answer(self):
        a, b = self.say("一"), self.say("二")
        self.assertEqual(self.dan().returncode, 0)
        r = run(LISTEN, "--ws", str(self.ws), "--last", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"(?s)^== %s\n> 一\nFAKE ANSWER to: 一.*\n== %s\n> 二\nFAKE ANSWER to: 二" % (re.escape(a), re.escape(b)))

    def test_follow_prints_new_answers(self):
        p = subprocess.Popen([LISTEN, "--ws", str(self.ws)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=env())
        time.sleep(0.5)
        name = self.say("跟著看")
        self.assertEqual(self.dan().returncode, 0)
        time.sleep(1)
        p.terminate()
        out, _ = p.communicate(timeout=10)
        self.assertIn("== %s\n> 跟著看\nFAKE ANSWER to: 跟著看" % name, out)


class TailNewlineTest(Base):
    def test_tool_result_newlines_not_literal(self):
        import json, sys
        sys.path.insert(0, str(ROOT / "extras" / "human" / "bin"))
        import aos_human as h
        stack = Path(h.stack_of(str(self.ws)))
        stack.mkdir(parents=True, exist_ok=True)
        t = h.Tail(str(self.ws))
        with open(stack / "history.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"role": "tool", "tool_call_id": "x", "content": "391\n"}) + "\n")
            f.write(json.dumps({"role": "tool", "tool_call_id": "y", "content": "a\nb\n"}) + "\n")
        self.assertEqual(t.lines(), ["[工具 回 391]", "[工具 回 a ⏎ b]"])


class ChatTest(Base):
    def test_two_questions_keep_history(self):
        r = run(CHAT, "--ws", str(self.ws), DAN, input="你好\n/status\n第二句\n//斜線開頭\n/bogus\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 3, r.stdout)              # stdout 只有三個答案
        self.assertTrue(lines[0].startswith("FAKE ANSWER to: 你好"))
        self.assertTrue(lines[1].startswith("FAKE ANSWER to: 第二句"))
        self.assertTrue(lines[2].startswith("FAKE ANSWER to: /斜線開頭"))
        self.assertIn("沒有這個指令", r.stderr)
        self.assertIn("最後一格 idle 退 10", r.stderr)          # /status 印在 stderr
        hist = (self.ws / ".stack" / "history.jsonl").read_text(encoding="utf-8")
        self.assertEqual(hist.count('"role": "user"'), 3)      # agent-dan：同一個 stack，三句接在同一段對話
        self.assertEqual(len(os.listdir(self.ws / "done")), 3)

    def test_agent_fails_then_run_resumes(self):
        r = run(CHAT, "--ws", str(self.ws), DAN, input="壞腦那題\n", AOS_BRAIN_URL=DEAD)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIn("agent-dan: BrainFailed", r.stderr)      # agent 的錯誤一行原樣看得到
        self.assertIn("agent 停了（停在 think 格、結束碼 1）", r.stderr)
        self.assertIn("還有 1 題沒答", r.stderr)
        r = run(CHAT, "--ws", str(self.ws), DAN, input="/run\n")   # 新開一個 chat：認得還沒答的那題，/run 接著做
        self.assertIn("已經有 1 題還沒答", r.stderr)
        self.assertTrue(r.stdout.startswith("FAKE ANSWER to: 壞腦那題"), r.stdout + r.stderr)

    def test_without_agent_waits_for_other_runner(self):
        p = subprocess.Popen([CHAT, "--ws", str(self.ws)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env())
        p.stdin.write("別人跑\n")
        p.stdin.flush()
        deadline = time.time() + 10
        while not os.listdir(self.ws / "new") if (self.ws / "new").exists() else True:
            self.assertLess(time.time(), deadline)
            time.sleep(0.1)
        time.sleep(1.5)
        self.assertEqual(self.dan().returncode, 0)
        out, err = p.communicate("", timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertTrue(out.startswith("FAKE ANSWER to: 別人跑"), out + err)
        self.assertIn("目前沒有程式在跑這個工作區", err)

    def test_agent_missing(self):
        r = run(CHAT, "--ws", str(self.ws), str(self.ws / "nope"), input="")
        self.assertRegex(r.stderr, r"^aos-chat: AgentMissing ")


if __name__ == "__main__":
    unittest.main()
