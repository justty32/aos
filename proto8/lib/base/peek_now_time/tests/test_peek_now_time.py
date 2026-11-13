"""Test peek_now_time: no arguments = UTC ending in Z; local true = local ISO with offset and weekday; bad local = ArgumentsBad."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"


def run(args):
    return subprocess.run([sys.executable, str(TOOL)], input=json.dumps(args), capture_output=True, text=True,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=30)


class PeekNowTime(unittest.TestCase):
    def test_utc(self):
        r = run({})
        self.assertEqual(r.returncode, 0, r.stderr)
        t = datetime.datetime.strptime(r.stdout.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        self.assertLess(abs((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds()), 5)

    def test_local(self):
        r = run({"local": True})
        self.assertEqual(r.returncode, 0, r.stderr)
        stamp, day = r.stdout.strip().split(" ")
        t = datetime.datetime.fromisoformat(stamp)
        self.assertIsNotNone(t.tzinfo)
        self.assertEqual(day, t.strftime("%A"))
        self.assertLess(abs((datetime.datetime.now().astimezone() - t).total_seconds()), 5)
        self.assertEqual(run({"local": False}).stdout.strip()[-1], "Z")

    def test_bad(self):
        r = run({"local": "yes"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("peek_now_time: error: ArgumentsBad", r.stdout)


if __name__ == "__main__":
    unittest.main()
