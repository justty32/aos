"""Test self_state builds aos-agent ctl state for the agent that calls it (overview, parts, all, json) with a fake aos-agent."""
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
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps([os.getcwd()] + sys.argv[1:]) + "\n")
if sys.argv[1:3] == ["ctl", "who"]:
    print("bob")
elif os.environ.get("FAKE_FAIL"):
    sys.stderr.write("aos-agent: error: InstanceMissing no agent named bob\n")
    sys.exit(1)
else:
    print("who       bob")
'''


class SelfState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="self-state-"))
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "aos-agent").write_text(FAKE)
        (bin_ / "aos-agent").chmod(0o755)
        self.log = self.tmp / "log"
        self.env = dict(os.environ, PATH="%s:%s" % (bin_, os.environ["PATH"]), AOS_WS=str(self.ws),
                        AOS_STACK=str(self.tmp / "st"), FAKE_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, args, **env):
        return subprocess.run([sys.executable, str(TOOL)], input=json.dumps(args), capture_output=True, text=True,
                              env=dict(self.env, **env), timeout=30)

    def last(self):
        return json.loads(self.log.read_text().splitlines()[-1])

    def test_each_call(self):
        base = ["ctl", "state", "--target", "bob"]
        for args, want in (({}, []), ({"json": True}, ["--json"]), ({"parts": ["history", "mailbox"]}, ["--", "history", "mailbox"]),
                           ({"parts": "all", "json": True}, ["--json", "--", "all"])):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            self.assertEqual(self.last()[1:], base + want, args)
            self.assertEqual(self.last()[0], str(self.ws))
            self.assertIn("who       bob", r.stdout)

    def test_bad_arguments(self):
        for args, word in (({"parts": ["nope"]}, "unknown part nope"), ({"parts": [1]}, "ArgumentsBad"),
                           ({"json": "yes"}, "ArgumentsBad"), ({"op": "ls"}, "ArgumentsBad")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout, args)

    def test_lower_error_passed_up(self):
        r = self.run_tool({}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("self_state: error: InstanceMissing no agent named bob", r.stdout)


if __name__ == "__main__":
    unittest.main()
