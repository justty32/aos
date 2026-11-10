"""Test the sweeper removes old <lock>.releasing.* leftovers (open-14) and leaves fresh, foreign and child-daemon ones alone."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "proto8" / "py"))
import aos_sweep  # noqa: E402


def leftover(parent, name, age_s):
    ns = int((time.time() - age_s) * 1e9)
    p = parent / ("%s.releasing.%020d.%d.%d" % (name, ns, 4242, 77))
    p.mkdir(parents=True)
    (p / "holder.json").write_text("{}")
    (p / ".reaping").mkdir()
    return p


class Releasing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-sweep-rel-")
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name) / "d"
        self.cell = self.d / "procs" / "worker"
        (self.cell / "queue").mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"worker": {"stack": "procs/worker", "phase": "stopped"}}}))

    def test_old_leftovers_go_fresh_and_foreign_stay(self):
        old_box = leftover(self.cell / "queue", "order.lock", 3600)
        old_top = leftover(self.d / "procs_requests", ".lock", 3600)
        fresh = leftover(self.cell / "queue", "order.lock", 5)
        foreign = self.cell / "queue" / "order.lock.releasing.notmine"
        foreign.mkdir()
        deep = leftover(self.cell / "procs" / "sub" / "queue", "order.lock", 3600)   # 子 daemon 的：不往下走
        dry = aos_sweep.sweep(str(self.d), "aos-sweeper", dry_run=True)
        self.assertEqual(sorted(a["dir"] for a in dry["releasing"]), sorted([str(old_box), str(old_top)]))
        self.assertTrue(old_box.exists())
        rep = aos_sweep.sweep(str(self.d), "aos-sweeper")
        self.assertEqual(len(rep["releasing"]), 2)
        self.assertFalse(old_box.exists())
        self.assertFalse(old_top.exists())
        for p in (fresh, foreign, deep):
            self.assertTrue(p.exists(), p)
        self.assertTrue(any("removed leftover lock folder" in s for s in aos_sweep.lines(rep)))


if __name__ == "__main__":
    unittest.main()
