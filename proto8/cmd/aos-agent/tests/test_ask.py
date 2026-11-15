"""Test aos-agent ask (say then wait for the answer to that letter; the subagent tool's op ask runs it): flags, stdin, timeout exit code, a fake agent's answer.
The fake agent here is a body not upgraded yet (no aos keys): the answer comes by the old matching, with a warning (reply-match-1114; upgraded bodies in test_reply_match)."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / "cmd" / "aos-agent"), str(PROTO / "py"), str(PROTO / "lib")]
import aos_agent  # noqa: E402
from aos_agent import ask, common, listen  # noqa: E402


class Stdin:
    """A piped stdin: not a terminal, bytes on .buffer."""
    def __init__(self, data):
        self.buffer = io.BytesIO(data)

    def isatty(self):
        return False


class Ask(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ask-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        for s in ("tmp", "new", "cur"):
            (self.tmp / "queue" / s).mkdir(parents=True)
        self.agent = SimpleNamespace(stack=str(self.tmp), name="kid", phase="running", row={"def": str(self.tmp / "def")})
        self.sent = []

    def fake_put(self, a, text, who):
        """Stands in for sender.put: drop one letter into queue/new/ (no aos-post needed)."""
        sig = "%012d.letter" % (len(self.sent) + 1)
        (self.tmp / "queue" / "new" / sig).mkdir()
        (self.tmp / "queue" / "new" / sig / "letter.json").write_text(json.dumps({"role": "user", "content": text}))
        self.sent.append((text, who))
        return sig

    def patches(self):
        return [patch.object(ask, "target", return_value=self.agent),
                patch.object(ask.sender, "put", side_effect=self.fake_put),
                patch.object(listen, "on_table", return_value=True),
                patch.object(listen, "label", return_value="running")]

    def run_main(self, *argv, stdin=None):
        """Run the real dispatcher (aos-agent ask ...) in process; return (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.ExitStack() as st:
            for p in self.patches():
                st.enter_context(p)
            st.enter_context(patch.object(sys, "argv", ["aos-agent", "ask", *argv]))
            if stdin is not None:
                st.enter_context(patch.object(sys, "stdin", stdin))
            st.enter_context(contextlib.redirect_stdout(out))
            st.enter_context(contextlib.redirect_stderr(err))
            try:
                aos_agent.main()
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def fake_agent(self, answer, delay=0.3):
        """A fake agent body: take the letter from new/ to cur/, write question and answer into history, move the letter out of the queue."""
        def body():
            time.sleep(delay)
            new = self.tmp / "queue" / "new"
            for _ in range(100):
                got = sorted(new.iterdir())
                if got:
                    break
                time.sleep(0.05)
            sig = got[0].name
            os.rename(new / sig, self.tmp / "queue" / "cur" / sig)
            q = json.loads((self.tmp / "queue" / "cur" / sig / "letter.json").read_text())
            with open(self.tmp / "history.jsonl", "a") as f:
                f.write(json.dumps(q) + "\n")
                f.write(json.dumps({"role": "assistant", "content": answer}) + "\n")
            os.rename(self.tmp / "queue" / "cur" / sig, self.tmp / ("done-" + sig))   # answered: out of the queue (moved, not deleted)
        t = threading.Thread(target=body, daemon=True)
        t.start()
        self.addCleanup(t.join, 10)
        return t

    # ------------------------------------------------------------ flags

    def test_wired_into_dispatcher(self):
        self.assertIs(aos_agent.SUBS["ask"], ask.cmd)
        self.assertIn("  ask ", aos_agent.HELP)

    def test_flags(self):
        cases = [(["--timeout-s", "1", "--timeout-cycles", "2", "hi"], "ArgumentsBad"),
                 (["--timeout-s", "-1", "hi"], "ArgumentsBad"),
                 (["--timeout-s", "nan", "hi"], "ArgumentsBad"),
                 (["--timeout-cycles", "0", "hi"], "ArgumentsBad"),
                 (["--last", "1", "hi"], "FlagUnknown")]
        for argv, want in cases:
            with self.subTest(argv=argv), self.assertRaises(common.Fail) as e:
                ask.cmd(argv)
            self.assertEqual(e.exception.code, want)
        with self.assertRaises(common.Fail) as e:
            ask.cmd(["--timeout-s", "x", "hi"])
        self.assertIn("usage: aos-agent [--daemon D] ask", str(e.exception))        # the usage is ask's, not listen's
        self.assertIn("0 = no limit", str(e.exception))

    def test_timeouts_passed_to_wait(self):
        for argv, want in ((["hi"], (None, None)), (["--timeout-s", "0", "hi"], (None, None)),
                           (["--timeout-s", "2.5", "hi"], (2.5, None)), (["--timeout-cycles", "7", "hi"], (None, 7))):
            with self.subTest(argv=argv), contextlib.ExitStack() as st:
                for p in self.patches():
                    st.enter_context(p)
                wait = st.enter_context(patch.object(ask, "wait_latest"))
                ask.cmd(argv)
                args, kw = wait.call_args
                self.assertEqual((args[1], kw["timeout_cycles"]), want)
                self.assertEqual(args[2], 0)                                         # answers counted before sending
                self.assertEqual((kw["letter"], kw["before_rows"]), ("%012d.letter" % len(self.sent), 0))   # the letter put returned; history rows before sending

    def test_words_after_first_are_the_message(self):
        with contextlib.ExitStack() as st:
            for p in self.patches():
                st.enter_context(p)
            st.enter_context(patch.object(ask, "wait_latest"))
            ask.cmd(["--from", "bob", "what", "-t", "x"])
        self.assertEqual(self.sent, [("what -t x", "bob")])

    # ------------------------------------------------------------ stdin

    def test_stdin_is_the_message(self):
        with contextlib.ExitStack() as st:
            for p in self.patches():
                st.enter_context(p)
            st.enter_context(patch.object(ask, "wait_latest"))
            st.enter_context(patch.object(sys, "stdin", Stdin("line one\nline two\n".encode())))
            ask.cmd(["--from", "bob"])
        self.assertEqual(self.sent, [("line one\nline two", "bob")])

    def test_empty_stdin_is_refused_and_nothing_sent(self):
        code, out, err = self.run_main(stdin=Stdin(b"\n"))
        self.assertEqual(code, 1)
        self.assertIn("error: ArgumentsBad the message is empty", err)
        self.assertEqual(self.sent, [])

    # ------------------------------------------------------------ waiting

    def test_timeout_exits_nonzero(self):
        t = time.monotonic()
        code, out, err = self.run_main("--timeout-s", "0.5", "hi")
        self.assertLess(time.monotonic() - t, 10)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("aos-agent: error: AnswerMissing waited 0.5 s", err)
        self.assertEqual([t for t, _ in self.sent], ["hi"])

    def test_prints_only_the_answer(self):
        self.fake_agent("it is noon")
        code, out, err = self.run_main("--timeout-s", "10", "what", "time?")
        self.assertEqual((code, out), (0, "it is noon\n"), err)
        self.assertIn("kid's body is not upgraded yet", err)
        self.assertEqual([t for t, _ in self.sent], ["what time?"])

    def test_old_answer_is_not_taken_for_the_new_one(self):
        (self.tmp / "history.jsonl").write_text(json.dumps({"role": "user", "content": "before"}) + "\n" +
                                                json.dumps({"role": "assistant", "content": "old answer"}) + "\n")
        self.fake_agent("new answer", delay=0.5)
        code, out, err = self.run_main("--timeout-s", "10", "again")
        self.assertEqual((code, out), (0, "new answer\n"), err)
        self.assertIn("not upgraded yet", err)

    def test_stdin_question_gets_answer(self):
        self.fake_agent("42")
        code, out, err = self.run_main("--timeout-s", "10", "-", stdin=Stdin(b"meaning of life?\n"))
        self.assertEqual((code, out), (0, "42\n"), err)
        self.assertIn("not upgraded yet", err)
        self.assertEqual([t for t, _ in self.sent], ["meaning of life?"])


if __name__ == "__main__":
    unittest.main()
