"""事件讀者手寫 fixture；保存端到位後再驗發布與中斷接續。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))

import contextlib
import io
import json  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest.mock import patch  # noqa: E402
from base import MODULES, HERE  # noqa: E402
from aos7_fs import Unknown, locked, write_json, read_json  # noqa: E402

EVENTS = os.path.join(MODULES, "events")
sys.path.insert(0, EVENTS)
import aos7_events_read as reader  # noqa: E402
import aos7_events_store as store  # noqa: E402
import aos7_events_cli as cli  # noqa: E402


def record(seq, **extra):
    """藍圖 §3 的完整事件。"""
    return dict({"v": 1, "stream": "a/obs", "seq": seq, "kind": "item", "capture": "published",
                 "source": {"node": "a", "round": seq, "run": 1}, "at": "2026-10-09T00:00:00+08:00",
                 "payload": {"item": seq}}, **extra)


class Fixtures(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aos72-events-")
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def segment(self, name, rows, tail=b""):
        with open(os.path.join(self.dir, name), "wb") as f:
            for row in rows:
                f.write(row if isinstance(row, bytes) else (json.dumps(row, ensure_ascii=False) + "\n").encode())
            f.write(tail)

    def state(self, **channel):
        write_json(os.path.join(self.dir, "state.json"), {"v": 1, "node": "a", "channels": {"obs": channel}})

    def seqs(self, result):
        return [r["seq"] for r in result["records"]]

    def cli(self, script, *args, env=None):
        p = subprocess.run([sys.executable, os.path.join(EVENTS, script), "--events", self.dir, *args],
                           capture_output=True, text=True, timeout=20, env=env)
        if p.returncode:
            self.assertEqual(len(p.stderr.splitlines()), 1, p.stderr)
            self.assertTrue(p.stderr.startswith("aos7-events: "), p.stderr)
            self.assertIn("。", p.stderr)
        return p


