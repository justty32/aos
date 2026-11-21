# Verify an agent-fsm /clear letter (line top-1121-apiclear) empties history into history_removed.jsonl without a brain call, with fake commands.
import json
import sys
import unittest

import test_compact as compact_tests
import test_reply_match as reply_tests

sys.dont_write_bytecode = True
import compact  # noqa: E402  (test_compact put the agent-fsm cells on sys.path)
from aos import ws as aos_ws  # noqa: E402

OLD = compact_tests.OLD


def note(n):
    return "[aos] slash: " + compact.CLEARED_NOTE % n


class SlashClear(unittest.TestCase):
    setUp = compact_tests.Compact.setUp
    command = reply_tests.ReplyMatch.command
    send = reply_tests.ReplyMatch.send
    letter = reply_tests.ReplyMatch.letter
    history = reply_tests.ReplyMatch.history
    letters = reply_tests.ReplyMatch.letters
    think = reply_tests.ReplyMatch.think
    run_cell = compact_tests.Compact.run_cell
    removed = compact_tests.Compact.removed

    def cur(self):
        return sorted(p.name for p in (self.stack / "queue/cur").iterdir() if not p.name.startswith("."))

    def assert_cleared(self, name, moved, text="/clear"):
        h = self.history()
        self.assertEqual(h, [{"role": "user", "content": text, "aos": {"letter": name}},
                             {"role": "assistant", "content": note(moved), "aos": {"answer_to": [name], "clear": True}}])
        self.assertEqual(aos_ws.answer_for(str(self.stack), name), ("answered", note(moved)))
        self.assertEqual(self.letters()["pending"], [])
        self.assertEqual(self.letters()["dropped"], [])
        self.assertFalse((self.stack / "mailbox_warning.txt").exists())
        self.assertFalse((self.root / "sent.json").exists())             # the brain was not asked

    def test_lone_clear_moves_history_and_answers(self):
        self.history(OLD)
        c = self.letter("  /clear\n")
        self.run_cell("idle", 10)                                       # nothing for the brain: back to idle
        self.assert_cleared(c, len(OLD), "  /clear\n")
        rows = self.removed()
        self.assertEqual([r["message"] for r in rows], OLD)
        self.assertEqual([(r["op"], r["line"]) for r in rows], [("clear", i) for i in range(1, len(OLD) + 1)])
        self.assertEqual(self.cur(), [])
        self.run_cell("brain", 10)                                      # the answer is the last message: nothing to answer

    def test_next_letter_starts_from_the_clean_history(self):
        self.history(OLD)
        self.letter("/clear")
        self.run_cell("idle", 10)
        b = self.letter("letter B")
        self.run_cell("idle")
        sent = self.think({"role": "assistant", "content": "answer B"})
        self.assertEqual([m.get("content") for m in sent if m["role"] != "system"],
                         ["/clear", note(len(OLD)), "letter B"])
        self.assertEqual(aos_ws.answer_for(str(self.stack), b), ("answered", "answer B"))

    def test_clear_with_more_words_is_a_plain_letter(self):
        self.history(OLD)
        name = self.letter("/clear the cache please")
        self.run_cell("idle")
        self.assertEqual(self.history()[-1], {"role": "user", "content": "/clear the cache please", "aos": {"letter": name}})
        self.assertEqual(self.removed(), [])

    def test_letters_before_clear_are_answered_first(self):
        self.history(OLD)
        a = self.letter("letter A")
        c = self.letter("/clear")
        b = self.letter("letter B")
        self.run_cell("idle")                                           # A goes to the brain; /clear and B wait in cur/
        self.assertEqual(self.history()[-1]["aos"], {"letter": a})
        self.assertEqual(self.cur(), sorted([c, b]))
        self.think({"role": "assistant", "content": "answer A"})
        (self.root / "sent.json").unlink()
        self.run_cell("idle", 10)                                       # /clear alone; B still waits
        self.assert_cleared(c, len(OLD) + 2)
        self.assertEqual(aos_ws.answer_for(str(self.stack), a), ("answered_removed", "answer A"))
        self.assertEqual(self.cur(), [b])
        self.run_cell("idle")
        self.assertEqual(self.history()[-1]["aos"], {"letter": b})
        self.assertEqual(len(self.history()), 3)

    def test_letters_after_clear_wait_for_the_next_idle(self):
        self.history(OLD)
        c = self.letter("/clear")
        b = self.letter("letter B")
        self.run_cell("idle", 10)
        self.assert_cleared(c, len(OLD))
        self.assertEqual(self.cur(), [b])
        self.run_cell("idle")
        self.assertEqual(len(self.history()), 3)

    def test_empty_history_and_bad_lines(self):
        c = self.letter("/clear")
        self.run_cell("idle", 10)
        self.assert_cleared(c, 0)
        self.assertEqual(self.removed(), [])
        (self.stack / "history.jsonl").write_text('{"role": "user", "content": "q"}\nnot json\n\n[1]\n')
        d = self.letter("/clear")
        self.run_cell("idle", 10)
        self.assertEqual(self.history()[-1]["content"], note(3))
        self.assertEqual([r.get("message", r.get("raw")) for r in self.removed()],
                         [{"role": "user", "content": "q"}, "not json", "[1]"])
        self.assertEqual(aos_ws.answer_for(str(self.stack), d), ("answered", note(3)))

    def test_clear_skips_queue_hooks(self):
        log = self.root / "hook.log"
        hook = self.defn / "count.py"
        hook.write_text("#!" + sys.executable + "\nimport sys\nopen(%r, 'a').write(sys.stdin.read() + '\\n')\n" % str(log))
        hook.chmod(0o755)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json", "llm": "llm.json"}, "hookeds": "hookeds.json"}))
        (self.defn / "hookeds.json").write_text(json.dumps({"q": {"event": "before_queue", "handler": "count.py"},
                                                            "a": {"event": "after_queue", "handler": "count.py"}}))
        self.history(OLD)
        self.letter("/clear")
        self.run_cell("idle", 10)
        self.assertFalse(log.exists())

    def test_goal_reminder_follows_like_after_any_answer(self):
        self.history(OLD)
        (self.stack / "goal.json").write_text(json.dumps({"text": "ship it", "status": "active", "reminded": 0, "limit": 5}))
        c = self.letter("/clear")
        self.run_cell("idle")                                           # goal untouched: its reminder follows the /clear answer
        h = self.history()
        self.assertEqual(len(h), 3)
        self.assertEqual(h[1]["aos"], {"answer_to": [c], "clear": True})
        self.assertTrue(h[2]["content"].startswith("[aos] goal:"), h[2])
        self.assertEqual(json.loads((self.stack / "goal.json").read_text())["text"], "ship it")


if __name__ == "__main__":
    unittest.main()
