"""Test aos-eca-turn's recognition of codex's "Replace goal?" menu (11-12 eca-slash /goal): only that menu with the cursor on "1. Replace current goal" counts, from a real screen capture."""
import types
import unittest

from test_switch import TURN

turn = types.ModuleType("aos_eca_turn")                       # the command runs main() at its end: load it without that line
turn.__file__ = str(TURN)
exec(compile(TURN.read_text(encoding="utf-8").replace("\naos_flags.run(main)", "\n"), str(TURN), "exec"), turn.__dict__)

# codex 0.167.2 screen (tmux capture-pane), a goal already active, then "/goal keep answering with the single word two, ..."
REAL = """• one
  Worked for 1s • 15:38
                                              Replace goal?
• one                                         New objective: keep answering with the single word two, take no
                                              other action
  Worked for 1s • 15:38
• one                                       › 1. Replace current goal  Set the new objective and start it now
                                              2. Cancel                Keep the current goal
  Worked for 1s • 15:38
                                              enter select · esc back
◦ Working (0s • esc to interrupt)
› Ask Codex to do anything
  GPT-6-Luna high · /tmp/slash-1112/cli-test                                     Pursuing goal (6s)
"""


class GoalReplace(unittest.TestCase):
    def test_real_menu_is_yes(self):
        self.assertEqual(turn.goal_replace_prompt(REAL), "yes")

    def test_cursor_on_cancel_is_not_pressed(self):
        moved = REAL.replace("› 1. Replace current goal", "  1. Replace current goal").replace("  2. Cancel", "› 2. Cancel")
        self.assertEqual(turn.goal_replace_prompt(moved), "other")

    def test_other_wording_is_not_pressed(self):
        self.assertEqual(turn.goal_replace_prompt(REAL.replace("Replace current goal", "Overwrite goal")), "other")

    def test_no_menu(self):
        self.assertIsNone(turn.goal_replace_prompt("• Goal active Objective: x\n› Ask Codex to do anything\n"))
        self.assertIsNone(turn.goal_replace_prompt(""))


if __name__ == "__main__":
    unittest.main()
