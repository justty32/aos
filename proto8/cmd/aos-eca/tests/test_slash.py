"""Test aos-eca-turn's slash commands (11-12 eca-slash): one letter that is exactly /clear, /compact, /status, /usage or /exit is done by aos (or handed to claude when claude -p knows it), with fake CLIs."""
import json
import unittest

from test_switch import Base


class ClaudeSlash(Base):
    def first_turn(self):
        self.say("hello")
        self.ok_turn()
        return self.sid()

    def answer(self):
        return self.history()[-1]["content"]

    def test_clear_moves_history_and_starts_new(self):
        old = self.first_turn()
        self.say("/clear")
        self.ok_turn()
        self.assertEqual(len(self.calls()), 1)                     # the CLI is not asked
        self.assertEqual(self.sid(), "")
        self.assertEqual([m["content"] for m in self.history()][0], "/clear")
        self.assertTrue(self.answer().startswith("[aos] slash: /clear: 2 messages moved to history_removed.jsonl"), self.answer())
        removed = [json.loads(l) for l in (self.stack / "history_removed.jsonl").read_text().splitlines()]
        self.assertEqual([r["message"]["content"] for r in removed], ["hello", "FAKE: hello"])
        self.assertEqual(self.queue(), [])
        self.say("again")
        r = self.ok_turn()
        self.assertNotIn("history.jsonl was changed", r.stderr)
        new = self.sid()
        self.assertTrue(new and new != old)
        self.assertNotIn("--resume", self.calls()[-1]["argv"])
        self.assertNotIn("hello", self.calls()[-1]["stdin"])       # the old talk is gone from the record

    def test_status_answers_without_cli(self):
        old = self.first_turn()
        self.say("  /status\n")
        self.ok_turn()
        self.assertEqual(len(self.calls()), 1)
        self.assertIn("[aos] slash: /status: claude", self.answer())
        self.assertIn(old, self.answer())
        self.assertIn("screen closed", self.answer())

    def test_compact_goes_to_claude_on_the_same_conversation(self):
        old = self.first_turn()
        self.say("/compact")
        self.ok_turn()
        last = self.calls()[-1]
        self.assertEqual(last["stdin"], "/compact")
        self.assertEqual(last["argv"][last["argv"].index("--resume") + 1], old)
        self.assertEqual(self.sid(), old)
        self.assertEqual(self.answer(), "FAKE: /compact")

    def test_compact_without_conversation(self):
        self.say("/compact")
        self.ok_turn()
        self.assertEqual(self.calls(), [])
        self.assertIn("no conversation yet", self.answer())

    def test_usage_is_a_separate_claude_call(self):
        old = self.first_turn()
        self.say("/usage")
        self.ok_turn()
        last = self.calls()[-1]
        self.assertEqual(last["stdin"], "/usage")
        self.assertIn("--no-session-persistence", last["argv"])
        self.assertNotIn("--resume", last["argv"])
        self.assertEqual(self.answer(), "FAKE: /usage")
        self.assertEqual(self.sid(), old)

    def test_exit_without_screen(self):
        self.say("/exit")
        self.ok_turn()
        self.assertIn("no screen is open", self.answer())

    def test_mixed_batch_is_plain_text(self):
        self.say("/clear", "hello")
        self.ok_turn()
        self.assertEqual(self.calls()[-1]["stdin"], "/clear\n\nhello")
        self.assertFalse((self.stack / "history_removed.jsonl").exists())


class CodexSlash(Base):
    kind = "codex"

    def test_compact_starts_a_new_thread_with_the_record(self):
        self.say("hello")
        self.ok_turn()
        old = self.sid()
        self.say("/compact")
        self.ok_turn()
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.sid(), "")
        self.assertIn("[aos] slash: /compact: codex cannot compact", self.history()[-1]["content"])
        self.say("again")
        self.ok_turn()
        self.assertNotEqual(self.sid(), old)
        self.assertIn("[user] hello", self.calls()[-1]["stdin"])

    def test_usage_and_clear(self):
        self.say("hello")
        self.ok_turn()
        self.say("/usage")
        self.ok_turn()
        self.assertIn("codex has no usage report", self.history()[-1]["content"])
        self.say("/clear")
        self.ok_turn()
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.sid(), "")
        self.assertEqual(len(self.history()), 2)


if __name__ == "__main__":
    unittest.main()
