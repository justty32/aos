"""test_add_rm_checks - aos-daemon-ctl add 撞名＝InstanceExists、rm 表上沒有＝ProcMissing，都報錯不寄（cli-sweep 甲5，11-10）。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROTO = Path(__file__).resolve().parents[3]
CTL = PROTO / "cmd" / "aos-daemon-ctl" / "bin" / "aos-daemon-ctl"


class AddRmChecks(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="addrm-")
        Path(self.d, "procs_state.json").write_text(json.dumps({"procs": {"job": {"phase": "running", "exec": "x"}}}) + "\n")
        self.body = os.path.join(self.d, "job")
        os.makedirs(self.body)
        Path(self.body, "_entry").write_text('{"exec": "run.sh", "interval_ms": 0}\n')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_ctl(self, *args):
        return subprocess.run([sys.executable, str(CTL), "-d", self.d, *args], capture_output=True, text=True)

    def test_add_same_name_is_refused(self):
        r = self.run_ctl("add", self.body)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("InstanceExists", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.d, "procs_requests")))     # nothing sent

    def test_rm_missing_name_is_refused(self):
        r = self.run_ctl("rm", "nobody")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("ProcMissing", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.d, "procs_requests")))


if __name__ == "__main__":
    unittest.main()
