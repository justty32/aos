"""Test clock_register wraps aos-clock-register for the calling agent: box left out = my own queue (fake aos-agent ctl who, real aos-clock and aos-post)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"
PROTO = TOOL.parents[3]
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["ctl", "who", "--json"]:
    print(json.dumps({"name": "ann", "stack": os.environ["FAKE_STACK"]}))
else:
    sys.stderr.write("aos-agent: error: ArgumentsBad unexpected\n"); sys.exit(1)
'''


class ClockRegisterTool(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clock-register-tool-"))
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "aos-agent").write_text(FAKE)
        (bin_ / "aos-agent").chmod(0o755)
        for n in ("ws", "root", "ann"):
            (self.tmp / n).mkdir()
        path = "%s:%s:%s" % (bin_, PROTO / "cmd" / "aos-clock-register" / "bin", os.environ["PATH"])
        self.clock = self.tmp / "root" / "clock"
        self.env = dict(os.environ, PATH=path, AOS_WS=str(self.tmp / "ws"), AOS_STACK=str(self.tmp / "ann" / "tools" / "x"),
                        AOS_CLOCK=str(self.clock), FAKE_STACK=str(self.tmp / "ann"), PYTHONDONTWRITEBYTECODE="1")
        subprocess.run(["aos-post", "init", str(self.tmp / "ann" / "queue")], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tool(self, args):
        return subprocess.run([sys.executable, str(TOOL)], input=json.dumps(args), capture_output=True, text=True,
                              env=self.env, timeout=30)

    def test_wake_me(self):
        self.assertEqual(self.tool({"op": "ls"}).stdout, "no entries\n")
        r = self.tool({"op": "add", "name": "wake", "every": 2, "text": "Time to check."})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("your own queue", r.stdout)
        self.assertIn("wake\t2\t", self.tool({"op": "ls"}).stdout)
        table = json.loads((self.tmp / "root" / "clock_register.json").read_text())["letters"]
        self.assertEqual(table["wake"]["by"], "ann")
        for _ in range(2):
            subprocess.run([sys.executable, str(PROTO / "cmd" / "aos-clock" / "bin" / "aos-clock"), str(self.clock)],
                           check=True, env=self.env)
        new = self.tmp / "ann" / "queue" / "new"
        letters = [json.loads((new / n / "letter.json").read_text()) for n in os.listdir(new)]
        self.assertEqual([l["body"]["content"] for l in letters], ["Time to check. (clock cycle 2)"])
        self.assertEqual(self.tool({"op": "rm", "name": "wake"}).stdout, "removed wake\n")

    def test_errors(self):
        r = self.tool({"op": "add", "name": "w", "every": 2, "text": "x", "color": "red"})
        self.assertIn("clock_register: error: ArgumentsBad unknown key color", r.stdout)
        self.assertIn("clock_register: error: OpUnknown", self.tool({"op": "set"}).stdout)
        self.assertIn("clock_register: error: EntryMissing", self.tool({"op": "rm", "name": "nope"}).stdout)
        self.assertIn("clock_register: error: ArgumentsBad", self.tool({"op": "add", "name": "w", "every": 0, "text": "x"}).stdout)


if __name__ == "__main__":
    unittest.main()
