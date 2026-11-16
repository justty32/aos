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
sys.path[:0] = [str(PROTO / "py"), str(PROTO / "lib"), str(PROTO / "cmd/aos-eca")]
from aos_eca import screen_slash as s


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
        self.assertTrue(all(c == ("capture-pane", "-p", "-J", "-S", "-300", "-t", s.cli_base.TMUX_SESSION)
                            for c in self.cell.calls[1:]))
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


if __name__ == "__main__":
    unittest.main()
