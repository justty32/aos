"""Test aos-agent peek on a fake daemon table (11-16 ok-small): it runs the definition's screen entry with peek COMMAND and passes its output and errors through."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
BIN = REPO / "proto8" / "bin" / "aos-agent"
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
if "/fail" in sys.argv:
    sys.stderr.write("aos-eca-screen: error: CliFailed claude -p /usage exited 1\n")
    sys.exit(1)
print(json.dumps({"argv": sys.argv[1:], "stack": os.environ.get("AOS_STACK"), "ws": os.environ.get("AOS_WS")}))
'''


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and not k.startswith("TC_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


class Peek(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="agent-peek-")))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        (self.defn / "screen").mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"screen": "screen"}}))
        (self.defn / "screen" / "interfaces.json").write_text(json.dumps({"aos-agent/screen": {}}))
        fake = self.tmp / "fake_screen"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        (self.defn / "screen" / "_entry").write_text(json.dumps([str(fake), "--eca", ".."]))
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"bob": {
            "phase": "running", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def agent(self, *args):
        return subprocess.run([str(BIN), "--daemon", str(self.d), "peek", "--target", "bob", *args],
                              env=clean_env(), capture_output=True, text=True, timeout=60, cwd=self.tmp, stdin=subprocess.DEVNULL)

    def test_runs_the_screen_entry(self):
        r = self.agent("/usage")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout)
        self.assertEqual(got["argv"], ["--eca", "..", "peek", "/usage"])
        self.assertEqual(os.path.realpath(got["stack"]), str(self.stack))
        self.assertEqual(os.path.realpath(got["ws"]), os.path.realpath(self.tmp / "ws"))

    def test_errors(self):
        r = self.agent("/fail")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-eca-screen: error: CliFailed", r.stderr)
        r = self.agent()
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-agent: error: ArgumentsBad", r.stderr)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}}))
        r = self.agent("/status")
        self.assertIn("aos-agent: error: ScreenMissing", r.stderr)


if __name__ == "__main__":
    unittest.main()
