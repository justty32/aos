# Check gitignore-check's local-path rule: which tracked contents count as a leak (B05/B06, 11-11).
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check  # noqa: E402

T = {"repo location": "/home/x/repo", "key prefix": "sk-"}


def leaks(name, text, mine=frozenset()):
    return check.leak_places(name, text.encode(), T, mine)


class Leaks(unittest.TestCase):
    def test_user_written_and_ledgers_pass(self):
        self.assertEqual(leaks("defs/a/tools.json", '{"p": "/home/x/repo/lib"}'), {})
        self.assertEqual(leaks("stacks/k/ledger.jsonl", '{"a": "/home/x/repo"}\n'), {})
        self.assertEqual(leaks("stacks/r/procs_state.json", '{"procs": {"a": {"as_written": {"ws": "/home/x/repo/w"}}}}'), {})
        self.assertEqual(leaks("stacks/k/requests/cur/l/letter.json", '{"sender": "/home/x/repo/w"}'), {})
        self.assertEqual(leaks("stacks/r/x.json", '{"ws": "/home/x/repo/w"}', {"/home/x/repo/w"}), {})

    def test_program_written_two_cells_pass(self):
        self.assertEqual(leaks("stacks/root/procs/f/state.json", '{"daemon": "/home/x/repo/stacks/root/"}'), {})
        self.assertEqual(leaks("stacks/root/procs/f/procs_state.json", '{"daemon": "/home/x/repo/stacks/root/"}'), {})
        self.assertEqual(leaks("stacks/k/requests/cur/l/proc.json", '{"exec": "/home/x/repo/defs/fake"}'), {})

    def test_other_cells_still_leak(self):
        self.assertEqual(leaks("stacks/r/x.json", '{"ws": "/home/x/repo/w"}'), {"repo location": ["/ws = /home/x/repo/w"]})
        self.assertIn("repo location", leaks("stacks/k/requests/cur/l/proc.json", '{"exec": "/a", "ws": "/home/x/repo/w"}'))
        self.assertIn("repo location", leaks("stacks/r/state.json", '{"procs": {"daemon": "/home/x/repo"}}'))   # only the top-level daemon
        self.assertIn("repo location", leaks("stacks/r/notes.txt", "/home/x/repo"))

    def test_key_prefix_always_checked(self):
        self.assertIn("key prefix", leaks("defs/a/tools.json", '{"k": "sk-abc"}'))
        self.assertIn("key prefix", leaks("stacks/k/ledger.jsonl", '{"k": "sk-abc"}\n'))
        self.assertIn("key prefix", leaks("defs/a/.env", "KEY=sk-abc\n"))

    def test_key_prefix_inside_a_word_is_not_a_key(self):
        self.assertEqual(leaks("defs/a/README.md", "see [x](../eca-task-subagent.md)\n"), {})


if __name__ == "__main__":
    unittest.main()
