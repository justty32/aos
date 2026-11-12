# Check gitignore_classes.json against paths today's tools write: each one classifies to the expected row (11-12 line K: fork children state, subagents.json).
from pathlib import Path
import json
import sys
from types import SimpleNamespace
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check  # noqa: E402

ROWS = json.loads((check.PROTO / "thinking/2026-11/10/two-machines/gitignore_classes.json").read_text())["rows"]


def row(path):
    found = check.Check.classify(SimpleNamespace(rows=ROWS), path)
    return found and (found["id"], found["in_git"])


class Classes(unittest.TestCase):
    def test_fork_children_state_is_carried(self):
        self.assertEqual(row("stacks/root/procs/worker/tools/fork/children/f-worker-20261112T000929015-312e/state"), ("G099", "進"))

    def test_fork_observed_ledgers_stay_out(self):
        self.assertEqual(row("stacks/root/procs/worker/tools/fork/observed/f-worker-1/observed.jsonl")[1], "不進")

    def test_subagents_ledger_and_quota_are_carried(self):
        self.assertEqual(row("stacks/root/procs/worker/tools/subagent/subagents.json"), ("G063", "進"))
        self.assertEqual(row("stacks/root/procs/worker/subagents.json"), ("G063", "進"))

    def test_old_names_are_unknown(self):
        self.assertIsNone(row("stacks/root/procs/worker/tools/subagent/children.json"))   # proto8 沒有舊版：舊名不分類
        self.assertIsNone(row("stacks/root/zzz_unknown.txt"))

    def test_ids_are_unique(self):
        ids = [r["id"] for r in ROWS]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
