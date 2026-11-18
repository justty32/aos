"""Test reply matching on the reading side (reply-match-1114): ask / chat / listen --letter get the answer to their own letter from upgraded bodies, fall back to the latest answer for bodies not upgraded yet, and the old readers still read the new history."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import reply_fixture as rf  # noqa: E402
from reply_fixture import aos_ws  # noqa: E402

OLD_WORDS = "body is not upgraded yet"


def wait_for(cond, s=10):
    end = time.monotonic() + s
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


class NewBody(unittest.TestCase):
    """Upgraded bodies write aos.letter / aos.answer_to / letters.json."""

    def test_two_askers_each_get_their_own(self):
        d = rf.Daemon(self)
        rf.Body(self, d.stack(), think_s=0.6)               # fsm: one letter per turn, the second waits in new/
        a = d.start("ask", "-t", "kid", "--timeout-s", "20", "alpha")
        b = d.start("ask", "-t", "kid", "--timeout-s", "20", "beta")
        (oa, ea), (ob, eb) = a.communicate(timeout=30), b.communicate(timeout=30)
        self.assertEqual((a.returncode, oa), (0, "re: alpha\n"), ea)
        self.assertEqual((b.returncode, ob), (0, "re: beta\n"), eb)
        self.assertNotIn(OLD_WORDS, ea + eb)
        self.assertEqual(aos_ws.letters_pending(str(d.stack())), [])

    def test_one_batch_one_answer_to_everyone(self):
        d = rf.Daemon(self)
        rf.Body(self, d.stack(), shape="eca", gather_s=0.8)
        a = d.start("ask", "-t", "kid", "--timeout-s", "20", "alpha")
        b = d.start("ask", "-t", "kid", "--timeout-s", "20", "beta")
        (oa, ea), (ob, eb) = a.communicate(timeout=30), b.communicate(timeout=30)
        self.assertEqual((a.returncode, b.returncode), (0, 0), ea + eb)
        self.assertEqual(oa, ob)
        self.assertIn(oa, ("re: alpha | beta\n", "re: beta | alpha\n"))
        answers = [m for m in aos_ws.history(str(d.stack())) if aos_ws.is_answer(m)]
        self.assertEqual(len(answers), 1)
        self.assertEqual(len(answers[0]["aos"]["answer_to"]), 2)

    def test_dropped_letters_are_reported_at_once(self):
        d = rf.Daemon(self)
        rf.Body(self, d.stack(), drop=lambda n, t: t if t in ("bad", "blocked") else None, fail=lambda t: t == "boom")
        for text, reason in (("bad", "bad"), ("blocked", "blocked"), ("boom", "failed")):
            with self.subTest(text=text):
                t = time.monotonic()
                r = d.agent("ask", "-t", "kid", "--timeout-s", "30", text)
                self.assertLess(time.monotonic() - t, 15)          # not waiting for the timeout
                self.assertEqual((r.returncode, r.stdout), (1, ""), r.stderr)
                self.assertIn("aos-agent: error: LetterDropped ", r.stderr)
                self.assertIn("(%s: " % reason, r.stderr)

    def test_answer_moved_out_of_history_is_still_found(self):
        d = rf.Daemon(self)

        def after(stack):                                    # like aos-agent history rm on the answer: copy to history_removed.jsonl, then shorten history
            rows = aos_ws.history(stack)
            with open(os.path.join(stack, aos_ws.REMOVED), "a") as f:
                f.write(json.dumps({"removed_at": "2026-11-14T00:00:00Z", "op": "rm", "line": len(rows), "message": rows[-1]}) + "\n")
            Path(stack, "history.jsonl").write_text("".join(json.dumps(m) + "\n" for m in rows[:-1]))

        rf.Body(self, d.stack(), after=after)
        r = d.agent("ask", "-t", "kid", "--timeout-s", "20", "where did it go")
        self.assertEqual((r.returncode, r.stdout), (0, "re: where did it go\n"), r.stderr)
        # ask may catch the answer in history before `after` moves it (both are fine); listen after the move must find it in history_removed
        stack = str(d.stack())
        deadline = time.monotonic() + 10
        while any(aos_ws.is_answer(m) for m in aos_ws.history(stack)) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(any(aos_ws.is_answer(m) for m in aos_ws.history(stack)), "the fake body did not move the answer out")
        name = aos_ws.history(stack)[0]["aos"]["letter"]
        r = d.agent("listen", "-t", "kid", "--letter", name, "--timeout-s", "5")
        self.assertEqual((r.returncode, r.stdout), (0, "re: where did it go\n"), r.stderr)
        self.assertIn("was moved out of history", r.stderr)

    def test_summarized_question_still_matches(self):
        d = rf.Daemon(self)

        def before_answer(stack):                            # self_history summarize over this turn's user row: the aos.letter row is gone
            rows = aos_ws.history(stack)
            Path(stack, "history.jsonl").write_text(json.dumps({"role": "user", "content": "[aos] summary: lines 1-%d, %d messages. asked" % (len(rows), len(rows))}) + "\n")

        rf.Body(self, d.stack(), before_answer=before_answer)
        r = d.agent("ask", "-t", "kid", "--timeout-s", "20", "fold me")
        self.assertEqual((r.returncode, r.stdout), (0, "re: fold me\n"), r.stderr)
        self.assertNotIn(OLD_WORDS, r.stderr)

    def test_chat_each_line_its_own_letter(self):
        d = rf.Daemon(self)
        rf.Body(self, d.stack(), think_s=0.1)
        r = d.agent("chat", "-t", "kid", input="one\ntwo\n")
        self.assertEqual((r.returncode, r.stdout), (0, "re: one\nre: two\n"), r.stderr)
        self.assertNotIn(OLD_WORDS, r.stderr)

    def test_listen_letter_waits_for_that_one(self):
        d = rf.Daemon(self)
        first = d.agent("say", "-t", "kid", "first").stdout.strip()
        second = d.agent("say", "-t", "kid", "second").stdout.strip()
        rf.Body(self, d.stack(), think_s=0.2)
        r = d.agent("listen", "-t", "kid", "--letter", first, "--timeout-s", "20")
        self.assertEqual((r.returncode, r.stdout), (0, "re: first\n"), r.stderr)
        r = d.agent("listen", "-t", "kid", "--letter", second, "--timeout-s", "20")
        self.assertEqual((r.returncode, r.stdout), (0, "re: second\n"), r.stderr)

    def test_listen_flags(self):
        d = rf.Daemon(self)
        for argv, word in ((["--letter", "x", "--last", "1"], "--letter is only for waiting"),
                           (["--letter", "a/b"], "--letter needs a letter name"),
                           (["--letter", ".hidden"], "--letter needs a letter name")):
            r = d.agent("listen", "-t", "kid", *argv)
            self.assertEqual(r.returncode, 1, argv)
            self.assertIn("ArgumentsBad", r.stderr)
            self.assertIn(word, r.stderr)

    def test_listen_without_letter_newest_in_queue(self):
        d = rf.Daemon(self)
        d.agent("say", "-t", "kid", "older")
        d.agent("say", "-t", "kid", "newer")
        p = d.start("listen", "-t", "kid", "--timeout-s", "20")
        time.sleep(0.5)
        rf.Body(self, d.stack(), think_s=0.3)
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, out), (0, "re: newer\n"), err)

    def test_listen_without_letter_last_pending(self):
        d = rf.Daemon(self)
        s = str(d.stack())
        aos_ws.letters_take(s, ["000000000001.q"])
        rf.append(s, aos_ws.mark_letter({"role": "user", "content": "taken"}, "000000000001.q"))
        rf.append(s, {"role": "assistant", "content": "unrelated old answer"})   # an answer that is not to it
        p = d.start("listen", "-t", "kid", "--timeout-s", "20")
        time.sleep(0.8)
        self.assertIsNone(p.poll())                         # still waiting: the latest answer is not the pending letter's
        rf.append(s, aos_ws.mark_answer({"role": "assistant", "content": "to the pending one"}, ["000000000001.q"]))
        aos_ws.letters_answered(s)
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, out), (0, "to the pending one\n"), err)

    def test_listen_without_letter_nothing_pending_prints_latest(self):
        d = rf.Daemon(self)
        rf.append(str(d.stack()), {"role": "user", "content": "q", "aos": {"letter": "x"}},
                  {"role": "assistant", "content": "the last one", "aos": {"answer_to": ["x"]}})
        r = d.agent("listen", "-t", "kid", "--timeout-s", "5")
        self.assertEqual((r.returncode, r.stdout), (0, "the last one\n"), r.stderr)


class OldBody(unittest.TestCase):
    """Bodies not upgraded yet (the main road in every tree swap window): no aos keys, no letters.json."""

    def test_ask_falls_back_fsm_and_eca(self):
        d = rf.Daemon(self, names=("old-fsm", "old-eca"))
        rf.append(str(d.stack("old-fsm")), {"role": "user", "content": "before"}, {"role": "assistant", "content": "old answer"})
        rf.Body(self, d.stack("old-fsm"), upgraded=False, shape="fsm", think_s=0.4)
        rf.Body(self, d.stack("old-eca"), upgraded=False, shape="eca", think_s=0.4)
        for name in ("old-fsm", "old-eca"):
            with self.subTest(name=name):
                r = d.agent("ask", "-t", name, "--timeout-s", "20", "hello " + name)
                self.assertEqual((r.returncode, r.stdout), (0, "re: hello %s\n" % name), r.stderr)
                self.assertIn("%s's %s" % (name, OLD_WORDS), r.stderr)
                self.assertFalse((d.stack(name) / "letters.json").exists())

    def test_chat_falls_back(self):
        d = rf.Daemon(self)
        rf.Body(self, d.stack(), upgraded=False, think_s=0.1)
        r = d.agent("chat", "-t", "kid", input="one\ntwo\n")
        self.assertEqual((r.returncode, r.stdout), (0, "re: one\nre: two\n"), r.stderr)
        self.assertEqual(r.stderr.count(OLD_WORDS), 2)

    def test_listen_letter_falls_back(self):
        d = rf.Daemon(self)
        name = d.agent("say", "-t", "kid", "early").stdout.strip()
        p = d.start("listen", "-t", "kid", "--letter", name, "--timeout-s", "20")    # starts while the letter is in the queue
        time.sleep(0.5)
        rf.Body(self, d.stack(), upgraded=False)
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, out), (0, "re: early\n"), err)
        self.assertIn(OLD_WORDS, err)
        late = d.agent("say", "-t", "kid", "late").stdout.strip()
        self.assertTrue(wait_for(lambda: len(aos_ws.answers(str(d.stack()))) == 2))
        r = d.agent("listen", "-t", "kid", "--letter", late, "--timeout-s", "5")   # already answered when listen starts
        self.assertEqual((r.returncode, r.stdout), (0, "re: late\n"), r.stderr)
        self.assertIn(OLD_WORDS, r.stderr)

    def test_listen_without_letter_old_rules(self):
        d = rf.Daemon(self)
        d.agent("say", "-t", "kid", "plain")
        p = d.start("listen", "-t", "kid", "--timeout-s", "20")
        time.sleep(0.3)
        rf.Body(self, d.stack(), upgraded=False)
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, out), (0, "re: plain\n"), err)
        self.assertNotIn(OLD_WORDS, err)                      # listen without a letter is the latest answer anyway

    def test_no_record_at_all_times_out_with_the_hint(self):
        d = rf.Daemon(self)
        rf.Body(self, d.stack(), upgraded=False, drop=lambda n, t: "bad")      # an old body drops it: nothing written anywhere
        r = d.agent("ask", "-t", "kid", "--timeout-s", "1.5", "lost")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("error: AnswerMissing waited 1.5 s;", r.stderr)
        self.assertIn("last state: unknown", r.stderr)
        self.assertIn("may not be upgraded yet", r.stderr)
        self.assertNotIn("LetterDropped", r.stderr)          # no letters.json = never a LetterDropped


class OldReaderNewWriter(unittest.TestCase):
    """The pre-change aos-agent (listen, ask = say + latest answer) reads histories with aos keys and letters.json the same way."""

    def test_old_listen_same_with_and_without_aos(self):
        base = rf.base_tree(self, "cmd/aos-agent", "py", "lib")   # the old commit still has cmd/; its aos-agent imports aos_flags from py/
        old_bin = base / "cmd" / "aos-agent" / "bin" / "aos-agent"
        outs = {}
        for upgraded in (True, False):
            d = rf.Daemon(self)
            rf.Body(self, d.stack(), upgraded=upgraded, shape="eca", think_s=0.3)
            got = []
            for text in ("one", "two"):
                r = d.agent("ask", "-t", "kid", "--timeout-s", "20", text, bin=old_bin)
                got.append((r.returncode, r.stdout))
            got.append(d.agent("listen", "-t", "kid", "--last", "2", bin=old_bin).stdout)
            got.append(d.agent("listen", "-t", "kid", "--timeout-s", "5", bin=old_bin).stdout)
            outs[upgraded] = got
            self.assertEqual((d.stack() / "letters.json").exists(), upgraded)
        self.assertEqual(outs[True], outs[False])
        self.assertEqual(outs[True][:2], [(0, "re: one\n"), (0, "re: two\n")])


if __name__ == "__main__":
    unittest.main()
