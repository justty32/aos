"""Test the wrap-up-then-compact path end to end with fake claude (11-15 compact-1115): context_wrap (on_clock) reads live.jsonl, sends a wrap-up letter, then a lone /compact, no repeats; /compact with instructions; /compact always a batch of its own."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_switch import Base

PROTO = Path(__file__).resolve().parents[4]
HANDLER = PROTO / "py" / "tools" / "agent" / "context_wrap"
WRAP = "[aos] context_wrap:"


class CompactAlone(Base):
    """/compact never shares a batch; /compact INSTRUCTIONS is handed to claude as it is."""

    def first_turn(self):
        self.say("hello")
        self.ok_turn()
        return self.sid()

    def test_compact_in_the_middle_waits_for_its_own_batch(self):
        old = self.first_turn()
        self.say("a", "/compact", "b")
        self.ok_turn()
        self.assertEqual(self.calls()[-1]["stdin"], "a")              # the letter before it goes first, alone
        self.assertEqual(len(self.queue()), 2)                        # /compact and b wait in cur/
        self.ok_turn()
        last = self.calls()[-1]
        self.assertEqual(last["stdin"], "/compact")
        self.assertEqual(last["argv"][last["argv"].index("--resume") + 1], old)
        self.assertEqual(self.history()[-1]["content"], "FAKE: /compact")
        self.ok_turn()
        self.assertEqual(self.calls()[-1]["stdin"], "b")
        self.assertEqual(self.queue(), [])

    def test_compact_first_goes_alone(self):
        self.first_turn()
        self.say("/compact", "x", "y")
        self.ok_turn()
        self.assertEqual(self.calls()[-1]["stdin"], "/compact")
        self.ok_turn()
        self.assertEqual(self.calls()[-1]["stdin"], "x\n\ny")          # the rest is one batch again

    def test_compact_with_instructions(self):
        old = self.first_turn()
        self.say("  /compact keep the open items  \n")
        self.ok_turn()
        last = self.calls()[-1]
        self.assertEqual(last["stdin"], "/compact keep the open items")
        self.assertEqual(last["argv"][last["argv"].index("--resume") + 1], old)
        self.assertEqual(self.sid(), old)

    def test_compact_lookalike_is_plain_text(self):
        self.first_turn()
        self.say("/compactly", "z")
        self.ok_turn()
        self.assertEqual(self.calls()[-1]["stdin"], "/compactly\n\nz")


class WrapThenCompact(Base):
    def setUp(self):
        super().setUp()
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"history": "history.jsonl"}, "hookeds": "hookeds.json"}))
        (self.defn / "hookeds.json").write_text(json.dumps({"context_wrap": {
            "event": "on_clock", "every_cycles": 1, "config": {"percent": 35}, "handler": str(HANDLER),
            "timeout_ms": 20000}}))
        self.clock = self.t / "clock"
        self.cycle = 0
        self.clock.write_text("0\n")
        self.extra["AOS_CLOCK"] = str(self.clock)

    def tick_turn(self, **env):
        self.cycle += 1
        self.clock.write_text("%d\n" % self.cycle)
        return self.ok_turn(**env)

    def state(self):
        p = self.stack / "hookeds" / "context_wrap" / "state.json"
        return json.loads(p.read_text()) if p.exists() else None

    def wraps(self):
        return [c for c in self.calls() if c["stdin"].startswith(WRAP)]

    def compacts(self):
        return [c for c in self.calls() if c["stdin"] == "/compact"]

    def test_over_the_limit_wraps_then_compacts_once(self):
        high = {"FAKE_CLI_USAGE": "400000/1000000"}
        self.say("hello")
        self.tick_turn(**high)                                         # live.jsonl now says 40%
        self.assertIsNone(self.state())
        self.tick_turn(**high)                                         # the hook sends the wrap-up letter; the same turn answers it
        self.assertEqual(len(self.wraps()), 1)
        text = self.wraps()[0]["stdin"]
        self.assertIn("40% full (400000 of 1000000 tokens; the limit is 35%)", text)
        self.assertIn("wrap-up done", text)
        self.assertIn(str(self.stack / "handoff.md"), text)
        self.assertEqual(self.state()["phase"], "wrapping")
        self.assertEqual(self.compacts(), [])
        self.tick_turn(**high)                                         # wrap-up answered, queue empty: a lone /compact
        self.assertEqual(self.calls()[-1]["stdin"], "/compact")
        self.assertIn("--resume", self.calls()[-1]["argv"])
        self.assertEqual(self.state()["phase"], "compacting")
        for _ in range(3):                                             # compacted: no reading of a later turn yet, nothing again
            self.tick_turn(**high)
        self.assertEqual(self.state()["phase"], "compacted")
        self.assertEqual((len(self.wraps()), len(self.compacts())), (1, 1))
        self.say("next")
        self.tick_turn(FAKE_CLI_USAGE="100000/1000000")                # after the compact: 10%
        self.tick_turn()
        self.assertEqual(self.state()["phase"], "idle")                # watching again
        self.assertEqual((len(self.wraps()), len(self.compacts())), (1, 1))
        self.say("big again")
        self.tick_turn(**high)
        self.tick_turn(**high)
        self.assertEqual(len(self.wraps()), 2)                         # over the limit again later = a new round

    def test_still_over_after_compact_does_not_repeat(self):
        high = {"FAKE_CLI_USAGE": "500000/1000000"}
        self.say("hello")
        for _ in range(4):
            self.tick_turn(**high)
        self.assertEqual(self.state()["phase"], "compacted")
        self.say("still big")
        for _ in range(4):
            self.tick_turn(**high)
        self.assertEqual((len(self.wraps()), len(self.compacts())), (1, 1))

    def test_compact_waits_for_an_empty_queue(self):
        high = {"FAKE_CLI_USAGE": "400000/1000000"}
        self.say("hello")
        self.tick_turn(**high)
        self.tick_turn(**high)                                         # wrap-up sent and answered
        self.say("one more", "and another")                            # letters wait in the queue
        self.tick_turn(**high)
        self.assertEqual(self.calls()[-1]["stdin"], "one more\n\nand another")
        self.assertEqual(self.compacts(), [])
        self.tick_turn(**high)
        self.assertEqual(self.calls()[-1]["stdin"], "/compact")

    def test_under_the_limit_does_nothing(self):
        self.say("hello")
        for _ in range(4):
            self.tick_turn(FAKE_CLI_USAGE="200000/1000000")
        self.assertEqual(len(self.calls()), 1)
        self.assertIsNone(self.state())

    def test_no_reading_does_nothing(self):
        self.say("hello")
        for _ in range(4):
            r = self.tick_turn()                                       # fake claude without usage: live.jsonl has no reading
            self.assertEqual(r.stderr, "")
        self.assertEqual(len(self.calls()), 1)
        self.assertIsNone(self.state())

    def test_limit_comes_from_the_hook_config(self):
        hooks = json.loads((self.defn / "hookeds.json").read_text())
        hooks["context_wrap"]["config"] = {"percent": 15}
        (self.defn / "hookeds.json").write_text(json.dumps(hooks))
        self.say("hello")
        self.tick_turn(FAKE_CLI_USAGE="200000/1000000")
        self.tick_turn(FAKE_CLI_USAGE="200000/1000000")
        self.assertEqual(len(self.wraps()), 1)
        self.assertIn("the limit is 15%", self.wraps()[0]["stdin"])


class ClaudeCompactHook(unittest.TestCase):
    """templates/agents/eca-claude/compact_hook: PreCompact prints what the summary keeps; SessionStart (compact) points at the handoff and adds handoff.md."""

    def run_hook(self, what, env):
        return subprocess.run([sys.executable, str(PROTO / "templates" / "agents" / "eca-claude" / "compact_hook"), what], input="{}",
                              capture_output=True, text=True, timeout=30, env=env)

    def test_pre_and_start(self):
        with tempfile.TemporaryDirectory() as root:
            env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
            r = self.run_hook("pre", env)
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            self.assertIn("every item still open", r.stdout)
            r = self.run_hook("start", env)
            self.assertEqual(r.returncode, 0)
            self.assertIn("[aos] compact: this conversation was just compacted", r.stdout)
            env["AOS_STACK"] = root
            Path(root, "handoff.md").write_text("doing X; open: Y\n")
            r = self.run_hook("start", env)
            self.assertIn(os.path.join(root, "handoff.md"), r.stdout)
            self.assertTrue(r.stdout.rstrip().endswith("doing X; open: Y"), r.stdout)
            self.assertEqual(self.run_hook("other", env).returncode, 0)


if __name__ == "__main__":
    unittest.main()
