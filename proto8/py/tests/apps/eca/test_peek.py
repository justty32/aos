"""Test aos-eca-screen peek (11-16 ok-small): /status and /usage answer at once, also mid-turn, without the queue, history, lock or screen."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import unittest

from test_switch import Base, HERE

SCREEN = HERE.parents[3] / "bin" / "aos-eca-screen"


class Peek(Base):
    def peek(self, *args, **env):
        return subprocess.run([str(SCREEN), "--eca", str(self.defn), "peek", *args], env=self.env(**env),
                              capture_output=True, text=True, timeout=60)

    def snapshot(self):
        return [p.read_bytes() if p.is_file() else None for p in (self.stack / "history.jsonl", self.stack / "letters.json")]

    def test_status_and_usage_touch_nothing(self):
        self.say("hello")
        self.ok_turn()
        before, queued = self.snapshot(), self.queue()
        r = self.peek("/status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("[aos] slash: /status: claude, model"), r.stdout)
        self.assertIn("conversation %s" % self.sid(), r.stdout)
        self.assertIn("history 2 messages", r.stdout)
        n = len(self.calls())
        r = self.peek("/usage")
        self.assertEqual((r.returncode, r.stdout), (0, "FAKE: /usage\n"), r.stderr)
        last = self.calls()[-1]
        self.assertEqual(len(self.calls()), n + 1)
        self.assertEqual(last["stdin"], "/usage")
        self.assertIn("--no-session-persistence", last["argv"])        # a separate call: the conversation is not resumed
        self.assertNotIn("--resume", last["argv"])
        self.assertEqual((self.snapshot(), self.queue()), (before, queued))
        r = subprocess.run([str(SCREEN), "peek", "/status", "--eca", str(self.defn)], env=self.env(),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)                      # --eca after the action, like open / close / watch

    def test_answers_while_the_cell_is_locked_and_busy(self):
        self.say("hello")
        self.ok_turn()
        (self.cell / "busy.txt").write_text("x")                     # the screen is answering
        with open(self.cell / "lock", "a") as f:                       # someone holds the cell (a turn in progress)
            fcntl.flock(f, fcntl.LOCK_EX)
            r = self.peek("/status")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = self.peek("/usage")
            self.assertEqual((r.returncode, r.stdout), (0, "FAKE: /usage\n"), r.stderr)

    def test_bad_arguments(self):
        for args in ((), ("/clear",), ("/compact",), ("/status", "x")):
            r = self.peek(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("aos-eca-screen: error: ArgumentsBad", r.stderr)

    def test_usage_failure_is_reported(self):
        r = self.peek("/usage", FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-eca-screen: error: CliFailed", r.stderr)


class PeekCodex(Base):
    kind = "codex"

    def test_codex_usage_says_why(self):
        r = subprocess.run([str(SCREEN), "--eca", str(self.defn), "peek", "/usage"], env=self.env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("codex has no usage report", r.stdout)


if __name__ == "__main__":
    unittest.main()
