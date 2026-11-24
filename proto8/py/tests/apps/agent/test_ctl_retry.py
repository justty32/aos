"""Test aos-agent ctl retry: clears the stack's cooldown.json and says what it cleared (fake daemon table, no daemon)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import env_helper  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
BIN = REPO / "proto8" / "bin" / "aos-agent"
COOL = {"failures": 4, "until": "2099-11-10T02:41:07Z", "at": "2026-11-10T02:33:07Z", "code": "BrainFailed",
        "reason": "aos-llm recv exited 1", "dropped": 0, "retry": True,
        "error": {"code": "EndpointFailed", "msg": "cannot connect to http://127.0.0.1:4000"}}


class CtlRetry(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ctl-retry-"))
        self.d = self.tmp / "d"
        rows = {"ann": {"phase": "running", "stack": "procs/ann"},
                "bob": {"phase": "stopped", "stack": "procs/bob", "reason": "exited 1"},
                "cat": {"phase": "running", "stack": "procs/cat"}}
        for n in rows:
            (self.d / "procs" / n).mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": rows}))
        (self.d / "procs" / "ann" / "cooldown.json").write_text(json.dumps(COOL))
        (self.d / "procs" / "bob" / "cooldown.json").write_text(json.dumps(dict({k: v for k, v in COOL.items() if k != "error"}, failures=1,
                                                                                 until="2000-01-01T00:00:00Z", code="CliFailed",
                                                                                 reason="claude exited 1")))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def agent(self, *args, ok=True):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "retry", *args], env=env_helper.clean_env(TZ="UTC"),
                           capture_output=True, text=True, timeout=30)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def test_clears_and_reports(self):
        out = self.agent("ann").stdout
        self.assertEqual(out, "cleared ann's cooldown: 4 failures in a row, it was waiting until 02:41:07; last error: "
                              "BrainFailed EndpointFailed cannot connect to http://127.0.0.1:4000; it tries again on its next round\n")
        self.assertFalse((self.d / "procs" / "ann" / "cooldown.json").exists())
        out = self.agent("ann").stdout
        self.assertEqual(out, "ann has no cooldown (%s); nothing to clear\n" % (self.d / "procs" / "ann" / "cooldown.json"))

    def test_stopped_due_and_target_flag(self):
        out = self.agent("--target", "bob").stdout
        self.assertEqual(out, "cleared bob's cooldown: 1 failure in a row, it was already due; last error: CliFailed "
                              "claude exited 1; it is stopped: aos-agent ctl start --target bob to carry on\n")
        self.assertTrue((self.d / "procs" / "ann" / "cooldown.json").exists())   # only the one asked for

    def test_errors_and_help(self):
        p = self.agent("nobody", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("InstanceMissing", p.stderr)
        p = self.agent("ann", "bob", ok=False)
        self.assertIn("ArgumentsBad", p.stderr)
        p = subprocess.run([str(BIN), "ctl", "--help"], env=env_helper.clean_env(), capture_output=True, text=True, timeout=30)
        self.assertIn("retry", p.stdout)
        p = self.agent("--help")
        self.assertIn("cooldown.json", p.stdout)
        self.assertTrue(p.stdout.isascii())


if __name__ == "__main__":
    unittest.main()
