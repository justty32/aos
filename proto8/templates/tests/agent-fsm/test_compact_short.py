# Verify a /compact with too little to fold is answered like a finished compact (user 11-20 "當成正常做完"), with fake commands.
import json
import sys
import unittest

import test_compact as compact_tests
import test_reply_match as reply_tests

sys.dont_write_bytecode = True
import compact  # noqa: E402  (test_compact put the agent-fsm cells on sys.path)
from aos import ws as aos_ws  # noqa: E402

OLD = compact_tests.OLD
CELLS = reply_tests.CELLS


class CompactShort(unittest.TestCase):
    setUp = compact_tests.Compact.setUp
    command = reply_tests.ReplyMatch.command
    send = reply_tests.ReplyMatch.send
    letter = reply_tests.ReplyMatch.letter
    history = reply_tests.ReplyMatch.history
    letters = reply_tests.ReplyMatch.letters
    run_cell = compact_tests.Compact.run_cell
    start_idle = compact_tests.Compact.start_idle

    def compacted(self):
        """OLD, then one real compact between turns: history = summary + compact done."""
        self.start_idle()
        self.run_cell("brain")
        self.run_cell("wait", 10)
        self.run_cell("wait", 11, FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "The work summary."}))
        self.run_cell("brain", 10)
        self.assertEqual(len(self.history()), 2)
        (self.root / "sent.json").unlink()

    def short_answer(self, name, count=2):
        self.assertEqual(aos_ws.answer_for(str(self.stack), name), ("answered", compact.SKIP % (count, compact.MIN_ROWS)))

    def quiet(self):
        self.assertFalse((self.stack / "mailbox_warning.txt").exists())
        self.assertEqual(self.letters()["dropped"], [])
        self.assertEqual(self.letters()["pending"], [])
        self.assertFalse((self.root / "sent.json").exists())          # the brain was not asked

    def test_second_compact_in_a_row_is_answered_not_dropped(self):
        self.compacted()
        c = self.letter("/compact")
        self.run_cell("idle", 10)
        self.short_answer(c)
        self.assertEqual(self.history()[-1]["aos"], {"answer_to": [c], "compact": True, "skipped": True})
        self.assertEqual(compact.state(str(self.stack))["phase"], "done")
        self.quiet()
        self.run_cell("brain", 10)                                        # nothing to answer: back to idle

    def test_many_in_a_row_never_fill_the_threshold(self):
        self.compacted()
        names = []
        for _ in range(4):
            names.append(self.letter("/compact"))
            self.run_cell("idle", 10)
        for name in names:
            self.short_answer(name)
        self.assertEqual(len(self.history()), 6)
        self.assertEqual(compact.foldable(str(self.stack), self.history(), aos_ws), 2)
        self.quiet()

    def test_plain_letter_between_compacts_again(self):
        self.compacted()
        self.letter("plain letter")
        self.run_cell("idle")
        self.run_cell("brain")
        self.run_cell("wait", 10)
        self.run_cell("wait", FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "plain answer"}))
        self.letter("/compact")
        self.run_cell("idle")
        self.assertTrue(compact.asking(str(self.stack), self.history()))

    def test_same_batch_letter_after_short_answer_is_still_answered(self):
        self.compacted()
        c = self.letter("/compact")
        b = self.letter("letter B")
        self.run_cell("idle")
        h = self.history()
        self.assertEqual([m.get("aos") for m in h[2:]], [{"answer_to": [c], "compact": True, "skipped": True}, {"letter": b}])
        self.short_answer(c)
        self.run_cell("brain")
        self.run_cell("wait", 10)
        self.run_cell("wait", FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "answer B"}))
        self.assertEqual(aos_ws.answer_for(str(self.stack), b), ("answered", "answer B"))

    def test_task_history_keeps_summary_after_short_answer(self):
        self.compacted()
        self.letter("/compact")
        self.run_cell("idle", 10)
        self.letter("letter B")
        self.run_cell("idle")
        self.run_cell("brain", 0, "--history", "task")
        messages = json.loads((self.stack / "think/request.json").read_text())["request"]["messages"]
        self.assertTrue(messages[0]["content"].startswith("[aos] summary:"))
        self.assertEqual(messages[-1]["content"], "letter B")

    def test_short_compact_still_skips_queue_hooks(self):
        log = self.root / "hook.log"
        hook = self.defn / "count.py"
        hook.write_text("#!" + sys.executable + "\nimport sys\nopen(%r, 'a').write(sys.stdin.read() + '\\n')\n" % str(log))
        hook.chmod(0o755)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json", "llm": "llm.json"}, "hookeds": "hookeds.json"}))
        (self.defn / "hookeds.json").write_text(json.dumps({"count": {"event": "before_queue", "handler": "count.py"}}))
        self.history(OLD[:2])
        self.letter("/compact")
        self.letter("plain")
        self.run_cell("idle")
        seen = [json.loads(line)["content"] for line in log.read_text().splitlines() if line.strip()]
        self.assertEqual(seen, ["plain"])


if __name__ == "__main__":
    unittest.main()
