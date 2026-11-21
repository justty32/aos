"""Test reply matching on the eca side (reply-match-1114): user rows carry aos.letter, the final answer carries aos.answer_to, and <stack>/letters.json keeps pending and dropped (bad, blocked, failed)."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_switch import TURN, Base  # noqa: E402

PROTO = HERE.parents[3]


class ReplyMatch(Base):
    def letters(self):
        return json.loads((self.stack / "letters.json").read_text())

    def dropped(self):
        return [(x["letter"], x["reason"]) for x in self.letters()["dropped"]]

    def send_raw(self, body):
        r = subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], input=json.dumps(body),
                           env=self.env(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_one_turn_many_letters_answer_all_in_order(self):
        self.say("a", "b", "c")
        sigs = self.queue()
        self.ok_turn()
        h = self.history()
        self.assertEqual([m.get("aos") for m in h], [{"letter": s} for s in sigs] + [{"answer_to": sigs}])
        self.assertEqual(self.letters(), {"pending": [], "dropped": []})

    def test_forged_aos_key_is_overwritten_other_keys_stay(self):
        sig = self.send_raw({"role": "user", "content": "hi", "aos": {"answer_to": ["someone-else"]}, "extra": 1})
        self.ok_turn()
        self.assertEqual(self.history()[0], {"role": "user", "content": "hi", "aos": {"letter": sig}, "extra": 1})

    def test_cli_failure_drops_the_letters_as_failed(self):
        self.say("x", "y")
        sigs = self.queue()
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("CliFailed", r.stderr)
        self.assertEqual(self.letters()["pending"], [])
        self.assertEqual(self.dropped(), [(s, "failed") for s in sigs])
        self.assertEqual([m.get("aos") for m in self.history()], [{"letter": s} for s in sigs])   # no answer row

    def test_bad_letter_is_dropped_as_bad(self):
        bad = self.send_raw({"role": "tool", "content": "nope"})
        self.say("fine")
        good = [s for s in self.queue() if s != bad]
        self.ok_turn()
        self.assertEqual(self.dropped(), [(bad, "bad")])
        self.assertEqual(self.history()[-1]["aos"], {"answer_to": good})

    def test_blocked_letter_is_dropped_as_blocked(self):
        hook = self.defn / "drop.py"
        hook.write_text("#!%s\nimport json, sys\nev = json.load(sys.stdin)\nsys.exit(10 if ev['content'] == 'spam' else 0)\n" % sys.executable)
        hook.chmod(0o755)
        (self.defn / "interfaces.json").write_text(json.dumps({"hookeds": "hookeds.json"}))
        (self.defn / "hookeds.json").write_text(json.dumps({"drop": {"event": "before_queue", "handler": "drop.py"}}))
        self.say("spam", "keep")
        spam, keep = self.queue()
        self.ok_turn()
        self.assertEqual(self.dropped(), [(spam, "blocked")])
        self.assertEqual([m.get("aos") for m in self.history()], [{"letter": keep}, {"answer_to": [keep]}])

    def test_slash_letter_gets_marked_and_answered_once(self):
        self.say("hello")
        self.ok_turn()
        self.say("/status")
        (sig,) = self.queue()
        self.ok_turn()
        h = self.history()
        self.assertEqual(h[-2]["aos"], {"letter": sig})
        self.assertEqual(h[-1]["aos"], {"answer_to": [sig]})
        self.assertEqual(sum(1 for m in h if sig in (m.get("aos") or {}).get("answer_to", [])), 1)
        self.assertEqual(self.letters()["pending"], [])

    def test_slash_clear_marks_the_letter_after_clearing(self):
        self.say("hello")
        self.ok_turn()
        self.say("/clear")
        (sig,) = self.queue()
        self.ok_turn()
        self.assertEqual([m.get("aos") for m in self.history()], [{"letter": sig}, {"answer_to": [sig]}])

    def test_history_sum_and_reseed_are_not_affected(self):
        self.say("hello")
        (first,) = self.queue()
        self.ok_turn()
        old = self.sid()
        self.say("again")
        r = self.ok_turn()
        self.assertNotIn("history.jsonl was changed", r.stderr)    # .history_sum is taken after the marked rows
        self.assertIn("--resume", self.calls()[-1]["argv"])
        self.assertEqual(self.sid(), old)
        mark = self.mark()                                          # another machine: new conversation that carries the record
        mark["machine"] = "some-other-machine"
        (self.cell / ".session_home").write_text(json.dumps(mark))
        self.say("third")
        self.ok_turn()
        stdin = self.calls()[-1]["stdin"]
        self.assertIn("[user] hello\n[assistant] FAKE: hello\n[user] again\n[assistant] FAKE: again\n", stdin)
        self.assertNotIn(first, stdin)
        self.assertNotIn("answer_to", stdin)

    def test_letters_take_cannot_write_stops_and_keeps_the_letter(self):
        (self.stack / "letters.json").mkdir()                       # os.replace onto a folder fails
        self.say("x")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-eca-turn: error: WriteFailed", r.stderr)
        self.assertEqual(self.history(), [])
        self.assertEqual(len(self.queue()), 1)

    def test_drop_cannot_write_only_warns(self):
        (self.stack / "letters.json").mkdir()
        self.send_raw({"role": "tool", "content": "nope"})
        r = self.ok_turn()
        self.assertIn("warning: cannot write", r.stderr)
        self.assertEqual(self.queue(), [])


class LiveMailMatch(Base):
    """live_mail (ok-wake): a letter written into the running CLI's stdin joins the same answer."""

    def setUp(self):
        super().setUp()
        self.sbin = self.t / "bin-stream"
        self.sbin.mkdir()
        (self.sbin / "claude").symlink_to(HERE / "fake_claude_stream")

    def env(self, **more):
        env = super().env(**more)
        if hasattr(self, "sbin"):
            env["PATH"] = "%s:%s" % (self.sbin, env["PATH"])
        return env

    def test_live_letter_is_in_the_same_answer_to(self):
        self.write_cfg({"live_mail": True})
        self.say("SLOW:3 first")
        (first,) = self.queue()
        p = subprocess.Popen([str(TURN), "--on-empty", "idle", str(self.defn)], env=self.env(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        end = time.time() + 10
        while time.time() < end and [c["line"] for c in self.calls()][:1] != ["SLOW:3 first"]:
            time.sleep(0.1)
        r = subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], env=self.env(), capture_output=True,
                           text=True, input=json.dumps({"role": "user", "content": "second"}))
        second = r.stdout.strip()
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertEqual([m.get("aos") for m in self.history()],
                         [{"letter": first}, {"letter": second}, {"answer_to": [first, second]}])
        self.assertEqual(json.loads((self.stack / "letters.json").read_text())["pending"], [])


class Helpers(unittest.TestCase):
    """common.letters_*: take stops (WriteFailed), drop and answered only warn."""

    @classmethod
    def setUpClass(cls):
        for p in (str(PROTO / "py"), str(PROTO / "py")):
            if p not in sys.path:
                sys.path.insert(0, p)

    def test_answered_cannot_write_only_warns(self):
        from aos.apps.eca import common
        with patch.object(common.aos_ws, "letters_answered", side_effect=OSError("disk full")), \
                patch("sys.stderr", new_callable=io.StringIO) as err:
            common.letters_answered("/nowhere", ["x"])
        self.assertIn("cannot write /nowhere/letters.json: disk full", err.getvalue())

    def test_take_cannot_write_is_writefailed(self):
        from aos.apps.eca import common
        with patch.object(common.aos_ws, "letters_take", side_effect=OSError("disk full")):
            with self.assertRaises(common.Fail) as got:
                common.letters_take("/nowhere", ["a"])
        self.assertEqual(got.exception.code, "WriteFailed")


if __name__ == "__main__":
    unittest.main()
