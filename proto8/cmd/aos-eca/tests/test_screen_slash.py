# test_screen_slash checks screen-only commands with a fake cell, clock and tmux output, never a real screen.
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "cmd/aos-eca")]
from aos_eca import screen_slash as s
from aos_eca import slash as sl

# claude 2.1.325's bottom box as capture-pane -p -e shows it (11-16 ok-small, a throwaway screen): placeholder dim, typed text plain.
RULE_LINE = "\x1b[38;5;244m" + "\u2500" * 60 + "\x1b[39m"
FOOT = "  \u23f5\u23f5 auto mode on (shift+tab to cycle)"
PLACEHOLDER = "\x1b[39m\u276f\xa0\x1b[2mTry\x1b[0m \x1b[2m\"create\x1b[0m \x1b[2ma\x1b[0m \x1b[2mutil\x1b[0m \x1b[2mlogging.py\x1b[0m \x1b[2mthat...\"\x1b[0m"


def box(*inside, above="\u25cf one"):
    return "\n".join([above, RULE_LINE, *inside, RULE_LINE, FOOT, ""])


EMPTY_BOX = box("\x1b[39m\u276f\xa0")


class Clock:
    def __init__(self):
        self.now = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Cell:
    def __init__(self, root, screens, alive=True, pane="claude", changing=False):
        self.root, self.screens, self.open, self.pane = root, screens, alive, pane
        self.changing = changing
        self.calls = []
        self.captures = 0
        self.box = EMPTY_BOX

    def alive(self):
        return self.open

    def file(self, name):
        return str(self.root / name)

    def tmux(self, *args):
        self.calls.append(args)
        if args[0] == "display-message":
            return SimpleNamespace(stdout=self.pane + "\n", returncode=0)
        if args[0] != "capture-pane":
            raise AssertionError("unexpected fake tmux command")
        if "-e" in args:                                   # the input-box check before typing
            return SimpleNamespace(stdout=self.box, returncode=0)
        self.captures += 1
        text = self.screens[min(self.captures - 1, len(self.screens) - 1)]
        if self.changing and self.captures > 1:
            text += "\nprogress %d" % self.captures
        return SimpleNamespace(stdout=text, returncode=0)


class ScreenSlash(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="screen-slash-"))
        self.clock = Clock()
        self.cell = Cell(self.root, ["old private conversation", "old private conversation\n> /context\ncontext report\n"])
        self.type_line = patch.object(s.cli_ask, "type_line").start()
        patch.object(s.time, "monotonic", self.clock.monotonic).start()
        patch.object(s.time, "sleep", self.clock.sleep).start()
        self.addCleanup(patch.stopall)

    def run_slash(self, command="/context", kind="claude"):
        return s.screen_slash(command, {"kind": kind}, self.cell, str(self.root))

    def test_closed_screen_is_not_opened(self):
        self.cell.open = False
        self.assertIn("a screen must be open", self.run_slash())
        self.type_line.assert_not_called()
        self.assertEqual(self.cell.calls, [])

    def test_busy_leaves_letter_alone(self):
        (self.root / "busy.txt").write_text("busy")
        self.assertIsNone(self.run_slash())
        self.type_line.assert_not_called()
        self.assertEqual(self.cell.calls, [])

    def test_only_claude(self):
        self.assertIn("only claude's screen", self.run_slash(kind="codex"))
        self.type_line.assert_not_called()
        self.assertEqual(self.cell.calls, [])

    def test_shell_is_never_typed_into(self):
        for shell in ("bash", "zsh", "sh", "fish", "dash"):
            with self.subTest(shell=shell):
                self.cell.pane = shell
                self.assertIn("nothing was typed", self.run_slash())
        self.type_line.assert_not_called()
        self.assertTrue(all(c[0] == "display-message" for c in self.cell.calls))

    def test_unknown_or_injected_command_is_not_typed(self):
        for command in ("/other", "/context; echo secret", "/context\nexit", "/context extra"):
            self.assertIn("not supported", self.run_slash(command))
        self.assertEqual(self.cell.calls, [])
        self.type_line.assert_not_called()

    def test_normal_waits_and_only_copies_new_lines(self):
        result = self.run_slash()
        self.assertEqual(result, "[aos] slash: /context: typed into the open screen; it printed:\ncontext report")
        self.assertEqual(self.clock.now, 1.5)
        self.type_line.assert_called_once_with(self.cell, next(iter(s.SCREEN_ONLY)))
        self.assertEqual(self.cell.calls[0], ("display-message", "-p", "-t", s.cli_base.TMUX_SESSION, "#{pane_current_command}"))
        self.assertEqual(self.cell.captures, 4)
        self.assertEqual(self.cell.calls[1], ("capture-pane", "-p", "-e", "-t", s.cli_base.TMUX_SESSION))
        self.assertTrue(all(c == ("capture-pane", "-p", "-J", "-S", "-300", "-t", s.cli_base.TMUX_SESSION)
                            for c in self.cell.calls[2:]))
        self.assertNotIn("old private conversation", result)

    def test_missing_echo_does_not_copy_screen(self):
        self.cell.screens = ["secret old text", "different secret old text"]
        result = self.run_slash()
        self.assertIn("command was not seen", result)
        self.assertNotIn("secret old text", result)
        self.assertEqual(self.clock.now, 8)

    def test_masks_all_reviewed_secret_shapes(self):
        secrets = ["sk-" + "a" * 24, "ghp_" + "B" * 24, "gho_" + "C" * 24,
                   "AIza" + "D" * 24, "xoxb-" + "e" * 20, "AKIA" + "F" * 16,
                   "G" * 24, "password-value", "token-value", "key-value", "secret-value"]
        text = "\n".join(secrets[:6] + ["Bearer " + secrets[6], "PASSWORD=" + secrets[7],
                           "API_TOKEN=" + secrets[8], "API_KEY=" + secrets[9], "APP_SECRET=" + secrets[10]])
        self.cell.screens[1] = "> /context\n" + text
        result = self.run_slash()
        for secret in secrets:
            self.assertNotIn(secret, result)
        self.assertEqual(result.count("[secret hidden]"), len(secrets))

    def test_private_key_drops_entire_output(self):
        self.cell.screens[1] = "> /context\nvisible text\n-----BEGIN PRIVATE KEY-----\nkey material"
        result = self.run_slash()
        self.assertIn("no screen text was copied", result)
        self.assertNotIn("visible text", result)
        self.assertNotIn("key material", result)

    def test_keeps_head_and_cuts_at_3800(self):
        text = "head\n" + "x" * 4000 + "END MUST BE CUT"
        self.cell.screens[1] = "> /context\n" + text
        result = self.run_slash()
        output = result.split("it printed:\n", 1)[1]
        self.assertEqual(output, text[:3800] + "\u2026(cut)")
        self.assertNotIn("END MUST BE CUT", result)

    def test_changing_screen_times_out_at_eight_seconds(self):
        self.cell.changing = True
        result = self.run_slash()
        self.assertEqual(self.clock.now, 8)
        self.assertEqual(self.cell.captures, 17)
        self.assertIn("progress 17", result)

    def test_echo_alone_is_not_completion(self):
        self.cell.screens = ["before", "> /context\n", "> /context\n", "> /context\n", "> /context\nlate report"]
        self.assertIn("late report", self.run_slash())
        self.assertEqual(self.clock.now, 2.5)

    def test_last_echo_and_footer_are_removed(self):
        self.cell.screens[1] = ("old\n> /context\nold output\n> /context\nnew report\n"
                                "\u256d\u2500\u256e\n\u2502 input /context\n\u2570\u2500\u256f\n? for shortcuts\n\n")
        result = self.run_slash()
        self.assertTrue(result.endswith("it printed:\nnew report"), result)
        self.assertNotIn("old output", result)
        self.assertNotIn("for shortcuts", result)



class InputBox(unittest.TestCase):
    """repo-aos 11-16: never type into a screen whose input box has someone's words (or cannot be read); never clear it with C-u."""

    def test_states_seen_on_a_real_screen(self):
        cases = {
            "empty after a turn": (EMPTY_BOX, "empty"),
            "dim placeholder": (box(PLACEHOLDER), "empty"),
            "placeholder in one dim run": (box("\x1b[39m\u276f\xa0\x1b[2mTry \"x\"\x1b[0m"), "empty"),
            "typed": (box("\x1b[39m\u276f\xa0half typed words"), "typed"),
            "one char": (box("\x1b[39m\u276f\xa0x"), "typed"),
            "second line typed": (box("\x1b[39m\u276f\xa0", "  more"), "typed"),
            "typed after dim": (box("\x1b[39m\u276f\xa0\x1b[2mTry\x1b[22m mine"), "typed"),
            "trust dialog": ("\n".join([RULE_LINE, " Accessing workspace:", " \u276f No, exit", "   Yes, I trust this folder", ""]), "unknown"),
            "no box": ("$ claude\nbye\n", "unknown"),
            "box without the mark": (box("  Do you want to proceed?"), "unknown"),
            "plain capture without escapes": (box("\u276f half"), "typed"),
            "typed in 24-bit colour": (box("\x1b[39m\u276f\xa0\x1b[38;2;100;200;50m/compact\x1b[39m"), "typed"),
            "typed in colour 2 of 256": (box("\x1b[39m\u276f\xa0\x1b[38;5;2mhi\x1b[39m"), "typed"),
            "colon parameters": (box("\x1b[39m\u276f\xa0\x1b[38:5:244mhi\x1b[39m"), "typed"),
            "dim then 24-bit colour with 0 and 22": (box("\x1b[39m\u276f\xa0\x1b[2m\x1b[38;2;0;22;9mTry\x1b[0m"), "empty"),
            "an empty line typed (Shift+Enter)": (box("\x1b[39m\u276f\xa0", ""), "typed"),
            "indented menu cursor": (box(" \u276f 1. Yes"), "unknown"),
            "old box with more under it": (box("\x1b[39m\u276f\xa0") + "\n".join(["$ ls", "a", "b", "c", ""]), "unknown"),
        }
        for name, (screen, want) in cases.items():
            with self.subTest(name):
                self.assertEqual(s.input_state(screen), want)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="screen-input-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cell = Cell(self.root, ["before", "> /context\nreport"])
        self.type_line = patch.object(s.cli_ask, "type_line").start()
        self.err = patch.object(sys, "stderr").start()   # the warning goes through aos_flags.warn
        self.addCleanup(patch.stopall)

    def test_context_waits_while_someone_typed(self):
        self.cell.box = box("\x1b[39m\u276f\xa0half typed")
        self.assertIsNone(s.screen_slash("/context", {"kind": "claude"}, self.cell, str(self.root)))
        self.type_line.assert_not_called()
        self.assertFalse(any("send-keys" in c for c in self.cell.calls))   # nothing cleared
        warned = "".join(c.args[0] for c in self.err.write.call_args_list)
        self.assertIn("input box has text", warned)
        self.assertTrue(warned.startswith("aos-eca-turn: warning: /context not typed"), warned)   # the program that runs it
        failed = SimpleNamespace(stdout="", returncode=1)
        with patch.object(self.cell, "tmux", side_effect=lambda *a: failed if "-e" in a else Cell.tmux(self.cell, *a)):
            self.assertFalse(s.input_clear(self.cell))

    def test_compact_and_goal_wait_while_someone_typed(self):
        cell = self.cell
        cell.alive = lambda: True
        cell.box = box("\x1b[39m\u276f\xa0half typed")
        on_screen = patch.object(sl, "on_screen", return_value="typed").start()
        args = (None, "ws", str(self.root), None, None)
        for command, body in (("/compact", "/compact"), ("/clear", "/clear"), ("/goal", "/goal ship it")):
            with self.subTest(command):
                self.assertEqual(sl.slash_turn(command, {"kind": "claude"}, cell, *args, [{"content": body}], "yield"), 0)
        self.type_line.assert_not_called()
        on_screen.assert_not_called()
        cell.box = EMPTY_BOX                                 # an empty box: typed as before
        try:
            sl.slash_turn("/compact", {"kind": "claude"}, cell, *args, [{"content": "/compact"}], "yield")
        except Exception:
            pass                                             # recording the answer needs a real queue; only the typing matters here
        on_screen.assert_called_once()
        on_screen.reset_mock()
        type_goal = patch.object(sl.cli_ask, "type_line").start()
        with patch.object(sl, "input_clear", side_effect=AssertionError("codex is not checked")):
            for command in ("/compact", "/goal"):
                try:
                    sl.slash_turn(command, {"kind": "codex"}, cell, *args, [{"content": command}], "yield")
                except Exception as e:                       # past the guard: whatever the rest does with these fakes
                    self.assertNotIsInstance(e, AssertionError)
        self.assertTrue(on_screen.called and type_goal.called)          # codex /compact and /goal both got past the guard


if __name__ == "__main__":
    unittest.main()
