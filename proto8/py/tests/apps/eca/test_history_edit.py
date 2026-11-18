"""Test aos-eca-turn's shrunk history edit (11-10 self-family): history.jsonl changed between turns or during one = the next turn starts a new conversation carrying the changed record, with the fake claude."""
import json
import unittest

from test_switch import Base


class HistoryEdit(Base):
    def first_turn(self):
        self.say("hello")
        self.ok_turn()
        self.assertTrue((self.cell / ".history_sum").read_text().strip())
        return self.sid()

    def test_unchanged_resumes(self):
        old = self.first_turn()
        self.say("again")
        r = self.ok_turn()
        self.assertEqual(self.sid(), old)
        self.assertNotIn("history.jsonl was changed", r.stderr)

    def test_changed_between_turns_starts_new_with_changed_record(self):
        old = self.first_turn()
        p = self.stack / "history.jsonl"
        p.write_text(json.dumps({"role": "user", "content": "summary: we said hello"}) + "\n")   # 人用 aos-agent history 改過
        self.say("again")
        r = self.ok_turn()
        self.assertIn("history.jsonl was changed since the last turn; starting a new claude conversation", r.stderr)
        new = self.sid()
        self.assertTrue(new and new != old)
        last = self.calls()[-1]
        self.assertNotIn("--resume", last["argv"])
        self.assertIn("--- record: 1 messages, 1 shown ---\n[user] summary: we said hello\n--- end of record ---\n\nagain",
                      last["stdin"])
        self.say("third")
        self.ok_turn()
        self.assertEqual(self.sid(), new)                        # 之後照常續新的那段

    def test_changed_during_turn_new_conversation_next_turn(self):
        old = self.first_turn()
        self.say("again")
        self.ok_turn(FAKE_CLI_DROP_FIRST=str(self.stack / "history.jsonl"))   # 這一輪中間腦叫 self_history 刪了第 1 行
        self.assertEqual((self.cell / ".history_sum").read_text().strip(), "edited")
        self.assertEqual(self.sid(), old)                        # 這一輪照舊答完
        self.say("third")
        r = self.ok_turn()
        self.assertIn("starting a new claude conversation", r.stderr)
        self.assertNotEqual(self.sid(), old)
        self.assertIn("[assistant] FAKE: hello\n[user] again\n[assistant] FAKE: again\n--- end of record ---\n\nthird",
                      self.calls()[-1]["stdin"])


if __name__ == "__main__":
    unittest.main()
