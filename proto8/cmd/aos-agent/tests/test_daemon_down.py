"""Test aos-agent ctl add/stop fail at once with DaemonMissing when the daemon's state window names a dead pid (cli-sweep 甲6), sending nothing."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
BIN = REPO / "proto8" / "cmd" / "aos-agent" / "bin" / "aos-agent"


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env.update(PYTHONDONTWRITEBYTECODE="1")
    return env


def dead_pid():
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


class DaemonDown(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="daemon-down-"))
        self.d = self.tmp / "d"
        (self.d / "procs" / "ann").mkdir(parents=True)
        for box in ("new", "cur", "tmp"):
            (self.d / "procs_requests" / box).mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"ann": {"phase": "running", "stack": "procs/ann"}}}))
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        (self.d / "state.json").write_text(json.dumps({"pid": dead_pid(), "started_at_ticks": 1, "boot_id": boot}))
        self.agent = self.tmp / "bob"
        self.agent.mkdir()
        (self.agent / "interfaces.json").write_text('{"aos-agent": {}}\n')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_agent(self, *args):
        t = time.monotonic()
        r = subprocess.run([sys.executable, str(BIN), "-d", str(self.d), *args], capture_output=True, text=True,
                           env=clean_env(), cwd=self.tmp, timeout=60)
        return r, time.monotonic() - t

    def assert_missing(self, r, took):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("error: DaemonMissing", r.stderr)
        self.assertIn("nothing was sent", r.stderr)
        self.assertIn("aos-exec --stack", r.stderr)
        self.assertLess(took, 10)                        # 不乾等 --timeout-s（預設 30）
        self.assertEqual(list((self.d / "procs_requests" / "new").iterdir()), [])

    def test_add(self):
        self.assert_missing(*self.run_agent("ctl", "add", "-w", str(self.tmp), str(self.agent)))

    def test_stop(self):
        self.assert_missing(*self.run_agent("-t", "ann", "ctl", "stop"))


if __name__ == "__main__":
    unittest.main()
