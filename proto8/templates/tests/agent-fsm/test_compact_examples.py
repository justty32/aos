# Verify the example compact handlers in templates/docs/compact-examples (compact cut 5, 11-25) on agent-fsm's real cells with a fake brain: restore_todo and restore_goal add text after the summary, handoff_summary folds without the brain.
import json
import sys
import unittest

import test_compact as compact_tests
import test_compact_clear as clear_tests
import test_compact_hooks as hooks_tests

sys.dont_write_bytecode = True
import compact  # noqa: E402  (test_compact put the agent-fsm cells on sys.path)

EXAMPLES = hooks_tests.PROTO / "templates" / "docs" / "compact-examples"
GOAL = {"text": "ship the report", "status": "active", "reason": "", "reminded": 0, "limit": 5,
        "set_by": "user", "updated_by": "user", "updated_at": "2026-11-25T00:00:00Z"}


class CompactExamples(unittest.TestCase):
    command = compact_tests.Compact.command
    send = compact_tests.Compact.send
    letter = compact_tests.Compact.letter
    history = compact_tests.Compact.history
    letters = compact_tests.Compact.letters
    run_cell = compact_tests.Compact.run_cell
    request = compact_tests.Compact.request
    removed = compact_tests.Compact.removed
    start_idle = compact_tests.Compact.start_idle
    setUp = hooks_tests.CompactHooks.setUp

    def use(self, *names):
        """Hook these examples on before_compact in the definition's hookeds.json, by absolute path (as a person would after copying them)."""
        table = {n: {"event": "before_compact", "handler": str(EXAMPLES / n), "timeout_ms": 10000} for n in names}
        (self.defn / "hookeds.json").write_text(json.dumps(table))

    def fold_by_brain(self):
        """/compact between turns; the fake brain writes the summary. Returns the history after the fold."""
        self.start_idle()
        self.run_cell("brain")
        self.run_cell("wait", 10)
        self.run_cell("wait", 11, FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "the work summary"}))
        return self.history()

    def test_examples_are_executable_and_describe_themselves(self):
        for name in ("restore_todo", "restore_goal", "handoff_summary"):
            p = EXAMPLES / name
            lines = p.read_text().splitlines()
            self.assertTrue(lines[0].startswith("#!"), name)
            self.assertTrue(lines[1].startswith("# %s - " % name), name)
            self.assertTrue(p.stat().st_mode & 0o111, name)
            self.assertIn(name, (EXAMPLES / "README.md").read_text())

    def test_restore_todo_and_goal_go_after_the_summary(self):
        todo = self.stack / "tools" / "todo"
        todo.mkdir(parents=True)
        (todo / "todo.json").write_text(json.dumps({"items": [{"text": "write tests", "status": "completed"},
                                                              {"text": "send the reply", "status": "pending"}]}))
        (self.stack / "goal.json").write_text(json.dumps(GOAL))
        self.use("restore_goal", "restore_todo")                         # name order: goal first, todo added after it
        h = self.fold_by_brain()
        self.assertIn("the work summary", h[0]["content"])
        self.assertEqual(h[1], {"role": "user", "content": compact.RESTORED +
                                "Your goal (active): ship the report\n\n"
                                "Your todo list (from the todo tool, as it was before the compact):\n"
                                "[x] write tests\n[ ] send the reply"})
        self.assertEqual(h[2]["aos"]["compact"], True)

    def test_restores_change_nothing_without_their_files(self):
        self.use("restore_goal", "restore_todo")
        h = self.fold_by_brain()
        self.assertEqual(len(h), 2)                                      # summary + the compact answer, no restored row
        self.assertEqual(compact.state(str(self.stack))["restored_chars"], 0)

    def test_handoff_summary_folds_without_the_brain(self):
        (self.stack / "handoff.md").write_text("## compact 2026-11-24 (3 messages)\n\nold summary\n"
                                               "## notes 2026-11-25\n\nworking on the report; next: tests\n")
        self.use("handoff_summary")
        self.history(clear_tests.long_history(6))
        c = self.letter("/compact")
        self.run_cell("idle")
        h = self.history()
        self.assertEqual(len(h), 2)
        self.assertIn("working on the report; next: tests", h[0]["content"])
        self.assertNotIn("old summary", h[0]["content"])
        self.assertEqual(h[1]["aos"], {"answer_to": [c], "compact": True})
        self.assertFalse((self.stack / "think/request.json").exists())  # the brain was not asked
        self.assertEqual(compact.state(str(self.stack))["by"], "handoff_summary")

    def test_handoff_summary_without_handoff_lets_the_brain_write(self):
        self.use("handoff_summary")
        h = self.fold_by_brain()
        self.assertIn("the work summary", h[0]["content"])
        self.assertEqual(compact.state(str(self.stack))["by"], "brain")


if __name__ == "__main__":
    unittest.main()
