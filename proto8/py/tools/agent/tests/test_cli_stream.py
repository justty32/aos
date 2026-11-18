"""驗 cli_stream（wake-1114 主案 S）：claude -p --input-format stream-json 的 stdin 先不關、回答途中投新信；併進同一輪、
result 之後再投＝多一輪、上限（封數、秒數）、逾時、管子斷了、is_error。CLI 用 cmd/aos-eca/tests/fake_claude_stream 代替，不叫模型。"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import cli_base, cli_stream  # noqa: E402

FAKE = Path(__file__).resolve().parents[4] / "cmd" / "aos-eca" / "tests" / "fake_claude_stream"


class Died(Exception):
    def __init__(self, code, reason):
        super().__init__("%s %s" % (code, reason))
        self.code = code


class More:
    """假的 queue：take 一次給一封；skip＝前 skip 次 take 回 []；ready＝回 False 時回 []；hold＝第一次真給信前先睡幾秒
    （讓 CLI 先退出，測管子斷了）。calls 記 (動作, 起行程後幾秒, 當時 live 裡有沒有 result)；unsent 的那封放回 queue 最前面。"""

    def __init__(self, letters, log, skip=0, ready=None, hold=0, probe=None):
        self.queue, self.calls, self.skip, self.ready, self.hold = list(letters), log, skip, ready, hold
        self.probe, self.takes, self.last, self.t0 = probe or (lambda: False), 0, None, time.time()

    def note(self, what):
        self.calls.append((what, time.time() - self.t0, self.probe()))

    def take(self):
        self.takes += 1
        self.note("take")
        if self.takes <= self.skip or (self.ready and not self.ready()) or not self.queue:
            return []
        if self.hold:
            time.sleep(self.hold)
            self.hold = 0
        self.last = self.queue.pop(0)
        return [("someone", self.last)]

    def sent(self):
        self.note("sent")

    def unsent(self):
        self.note("unsent")
        self.queue.insert(0, self.last)

    def count(self, what):
        return sum(1 for c in self.calls if c[0] == what)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cli-stream-"))       # 不刪：留在 /tmp
        (self.tmp / "bin").mkdir()
        self.claude = self.tmp / "bin" / "claude"
        self.claude.symlink_to(FAKE)
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.live = self.tmp / "live.jsonl"
        self.log = []
        self.patch = patch.object(cli_base, "die", side_effect=lambda code, reason: (_ for _ in ()).throw(Died(code, reason)))
        self.patch.start()
        self.t0 = time.time()

    def tearDown(self):
        self.patch.stop()
        self.assertLess(time.time() - self.t0, 10)

    def argv(self):
        return [str(self.claude), "-p", "--output-format", "stream-json", "--verbose"] + cli_stream.MID_FLAGS

    def has_result(self):
        return self.live.exists() and '"type": "result"' in self.live.read_text(encoding="utf-8")

    def more(self, letters, **kw):
        return More(letters, self.log, probe=self.has_result, **kw)

    def run_mid(self, prompt, seconds=8, more=None, env=None, cap=None):
        env = dict(env or {}, FAKE_CLI_LOG=str(self.tmp / "cli.log"))
        return cli_stream.run_claude_stream_mid(self.argv(), prompt, str(self.ws), seconds, str(self.live),
                                                handed=lambda: self.log.append(("handed", 0, False)),
                                                env=env, more=more, cap=cap)

    def results(self, lines):
        return [ev for ev in cli_stream.events(lines) if ev.get("type") == "result"]

    def received(self):
        path = self.tmp / "cli.log"
        return [json.loads(l)["line"] for l in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


class TestMid(Base):
    def test_a_no_more(self):
        code, lines = self.run_mid("hello")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.results(lines)), 1)
        self.assertEqual(cli_stream.results_text(lines), "FAKE: hello")
        self.assertEqual(self.live.read_text(encoding="utf-8"), "".join(lines))
        self.assertEqual(self.received(), ["hello"])
        self.assertEqual([c[0] for c in self.log], ["handed"])

    def test_a_handed_before_take(self):
        more = self.more([])
        code, lines = self.run_mid("hello", more=more)
        self.assertEqual(code, 0)
        names = [c[0] for c in self.log]
        self.assertEqual(names.count("handed"), 1)
        self.assertEqual(names[0], "handed")
        self.assertIn("take", names)

    def test_b_merge_into_round(self):
        more = self.more(["m1", "m2"])
        code, lines = self.run_mid("SLOW:2 go", more=more)
        self.assertEqual(code, 0)
        res = self.results(lines)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["result"], "FAKE: SLOW:2 go | m1 | m2")
        self.assertEqual(more.count("sent"), 2)
        self.assertEqual(more.queue, [])
        self.assertEqual(self.received(), ["SLOW:2 go", "m1", "m2"])

    def test_c_after_result_second_round(self):
        more = self.more(["late"], ready=self.has_result)
        code, lines = self.run_mid("first", more=more)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.results(lines)), 2)
        self.assertEqual(cli_stream.results_text(lines), "FAKE: first\n\nFAKE: late")
        self.assertEqual(more.count("sent"), 1)

    def test_c_skip_takes(self):
        more = self.more(["late"], skip=1000)                        # 前 k 次都回 []：這輪一直沒信、照常收尾
        code, lines = self.run_mid("first", more=more)
        self.assertEqual((code, len(self.results(lines)), more.queue), (0, 1, ["late"]))

    def test_d_cap_letters(self):
        more = self.more(["m%d" % i for i in range(7)])
        code, lines = self.run_mid("SLOW:1 go", more=more)
        self.assertEqual(code, 0)
        self.assertEqual(more.count("sent"), 5)
        self.assertEqual(more.queue, ["m5", "m6"])
        self.assertEqual(self.received(), ["SLOW:1 go", "m0", "m1", "m2", "m3", "m4"])
        self.assertEqual(len(self.results(lines)), 1)

    def test_e_cap_seconds(self):
        t0 = time.time()
        more = self.more(["late"], ready=lambda: time.time() - t0 > 1.5)
        code, lines = self.run_mid("SLOW:2 go", more=more, cap={"letters": 5, "seconds": 1})
        self.assertEqual(code, 0)
        self.assertEqual(more.count("sent"), 0)
        self.assertEqual(more.queue, ["late"])
        self.assertEqual(cli_stream.results_text(lines), "FAKE: SLOW:2 go")
        self.assertFalse([c for c in self.log if c[0] == "take" and c[1] > 1.2])

    def test_f_timeout(self):
        t0 = time.time()
        more = self.more(["late"], ready=lambda: time.time() - t0 > 1.2)
        with self.assertRaises(Died) as e:
            self.run_mid("SLOW:5 go", seconds=1, more=more)
        self.assertEqual(e.exception.code, "CliFailed")
        self.assertEqual(more.count("sent"), 0)
        self.assertLess(time.time() - t0, 3)

    def test_g_broken_pipe(self):
        more = self.more(["late"], ready=self.has_result, hold=0.5)  # 給信前先睡：CLI 已經退出
        code, lines = self.run_mid("first", more=more, env={"FAKE_STREAM_DIE_AFTER": "1"})
        self.assertEqual(code, 0)
        self.assertEqual(more.count("sent"), 0)
        self.assertEqual(more.count("unsent"), 1)
        self.assertEqual(more.queue, ["late"])
        self.assertEqual(len(self.results(lines)), 1)

    def test_h_is_error(self):
        more = self.more(["m1"], ready=self.has_result)
        code, lines = self.run_mid("first", more=more, env={"FAKE_STREAM_FAIL": "1"})
        self.assertEqual(code, 1)
        res = self.results(lines)
        self.assertEqual(len(res), 1)
        self.assertTrue(res[0]["is_error"])
        self.assertFalse([c for c in self.log if c[0] == "take" and c[2]])     # 看到 result 之後沒再 take
        self.assertEqual(more.queue, ["m1"])
        self.assertEqual(cli_stream.results_text(lines), "usage limit reached")

    def test_missing_cli(self):
        with self.assertRaises(Died) as e:
            cli_stream.run_claude_stream_mid([str(self.tmp / "bin" / "nope")], "x", str(self.ws), 5, str(self.live))
        self.assertEqual(e.exception.code, "CliMissing")

    def test_session_id_and_line_shape(self):
        argv = self.argv() + ["--session-id", "abc-123"]
        code, lines = cli_stream.run_claude_stream_mid(argv, "中文 hi", str(self.ws), 5, str(self.live))
        self.assertEqual(code, 0)
        init = next(cli_stream.events(lines))
        self.assertEqual((init["subtype"], init["session_id"]), ("init", "abc-123"))
        self.assertIn("FAKE: 中文 hi", cli_stream.results_text(lines))


class TestStall(Base):
    def test_j_line_never_taken_closes_after_stall(self):
        more = self.more(["ghost"], ready=self.has_result)          # result 之後才投；假 CLI 吞掉、不回執也不回答
        with patch.object(cli_stream, "STALL", 1):
            t = time.time()
            code, lines = self.run_mid("first", more=more, env={"FAKE_STREAM_SWALLOW": "ghost"})
        self.assertEqual((code, len(self.results(lines)), more.count("sent")), (0, 1, 1))
        self.assertLess(time.time() - t, 5)                         # 不是等到 8 秒逾時才收
        self.assertEqual(self.received(), ["first", "ghost"])


class TestBackground(Base):
    def test_k_letter_while_background_task_runs(self):
        more = self.more(["late"], ready=self.has_result)          # 第一個 result（started）之後才給，那時背景任務還在跑
        code, lines = self.run_mid("BG:2 go", more=more)
        self.assertEqual(code, 0)
        self.assertEqual(cli_stream.results_text(lines), "FAKE: started\n\nFAKE: done | late")
        self.assertEqual((more.count("sent"), more.queue), (1, []))

    def test_k_no_letter_closes_after_background_ends(self):
        t = time.time()
        code, lines = self.run_mid("BG:1 go", more=self.more([]))
        self.assertEqual((code, len(self.results(lines))), (0, 2))
        self.assertLess(time.time() - t, 5)

    def test_k_stall_waits_while_background_runs(self):
        with patch.object(cli_stream, "STALL", 0.5):                # 背景任務 2 秒裡 stdout 安靜：不能提早關
            code, lines = self.run_mid("BG:2 go", more=self.more(["late"], ready=self.has_result))
        self.assertEqual(cli_stream.results_text(lines), "FAKE: started\n\nFAKE: done | late")


class TestAnswer(unittest.TestCase):
    @staticmethod
    def L(*evs):
        return [json.dumps(e) + "\n" for e in evs]

    ECHO = {"type": "user", "isReplay": True, "message": {"role": "user", "content": "x"}}

    @staticmethod
    def say(*blocks):
        return {"type": "assistant", "message": {"content": [{"type": "text", "text": b} if isinstance(b, str) else b for b in blocks]}}

    TOOL = {"type": "tool_use", "name": "Edit", "input": {}}

    def test_reply_to_mid_letter_before_next_tool_is_kept(self):
        lines = self.L(self.ECHO, self.say("Reading first.", self.TOOL), self.ECHO, self.say("6*7 is 42. Continuing."),
                       self.say(self.TOOL), self.say("EDITED 3"), {"type": "result", "result": "EDITED 3"})
        self.assertEqual(cli_stream.answer_text(lines), "6*7 is 42. Continuing.\n\nEDITED 3")

    def test_no_mid_letter_is_just_the_result(self):
        lines = self.L(self.ECHO, self.say("Reading first.", self.TOOL), self.say("done"), {"type": "result", "result": "done"})
        self.assertEqual(cli_stream.answer_text(lines), "done")

    def test_second_round_reply_equal_to_result_is_not_doubled(self):
        lines = self.L(self.ECHO, {"type": "result", "result": "one"}, self.ECHO, self.say("two"), {"type": "result", "result": "two"})
        self.assertEqual(cli_stream.answer_text(lines), "one\n\ntwo")

    def test_text_after_a_tool_is_not_collected(self):
        lines = self.L(self.ECHO, self.ECHO, self.say(self.TOOL), self.say("mid chatter"), self.say(self.TOOL),
                       {"type": "result", "result": "final"})
        self.assertEqual(cli_stream.answer_text(lines), "final")

    def test_bad_lines_and_unfinished_round(self):
        lines = ["not json\n"] + self.L(self.ECHO, self.ECHO, self.say("late words"))
        self.assertEqual(cli_stream.answer_text(lines), "late words")


class TestPure(unittest.TestCase):
    def test_user_line(self):
        line = cli_stream.user_line("中文\n第二行")
        self.assertTrue(line.endswith("\n"))
        self.assertEqual(line.count("\n"), 1)
        self.assertIn("中文", line)
        self.assertEqual(json.loads(line), {"type": "user", "message": {"role": "user", "content": "中文\n第二行"}})

    def test_results_text(self):
        lines = ['{"type": "system", "subtype": "init"}\n', "not json\n", '{"type": "result", "result": "one"}\n',
                 '{"type": "result", "result": ""}\n', '{"type": "result", "result": null}\n', "[1, 2]\n",
                 '{"type": "assistant", "result": "no"}\n', '{"type": "result", "result": "two"}']
        self.assertEqual(cli_stream.results_text(lines), "one\n\ntwo")
        self.assertEqual(cli_stream.results_text([]), "")
        self.assertEqual(cli_stream.results_text(["{bad"]), "")


if __name__ == "__main__":
    unittest.main()
