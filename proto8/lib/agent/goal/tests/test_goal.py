"""Test the goal tool builds the aos-agent goal command line for each op (get, set, done, pause, resume), checks its arguments and passes errors on, with a fake aos-agent."""
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
data = sys.stdin.read() if "-" in sys.argv[1:] else None
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps([os.getcwd(), data] + sys.argv[1:]) + "\n")
if sys.argv[1:3] == ["ctl", "who"]:
    print("bob")
elif os.environ.get("FAKE_FAIL"):
    sys.stderr.write("aos-agent: error: GoalMissing bob has no goal (set one with aos-agent goal set TEXT)\n")
    sys.exit(1)
else:
    print("status\tactive")
'''


class GoalTool(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="goal-tool-"))
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

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_each_op(self):
        for args, want, stdin in (({"op": "get"}, ["get"], None),
                                  ({"op": "set", "text": " Fix the test. "}, ["set", "-"], "Fix the test."),
                                  ({"op": "set", "text": "x", "limit": 3}, ["set", "--limit", "3", "-"], "x"),
                                  ({"op": "done", "reason": "it passes"}, ["done", "--", "it passes"], None),
                                  ({"op": "done", "status": "abandoned", "reason": "-x"}, ["done", "--abandoned", "--", "-x"], None),
                                  ({"op": "pause", "reason": "waiting for amy"}, ["pause", "--", "waiting for amy"], None),
                                  ({"op": "resume"}, ["resume"], None)):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            self.assertEqual(r.stdout, "status\tactive\n")
            who, call = self.calls()[-2:]
            self.assertEqual(who[2:], ["ctl", "who"])
            self.assertEqual(call[2:], ["goal", "--target", "bob"] + want, args)
            self.assertEqual(call[0], str(self.ws))
            self.assertEqual(call[1], stdin)

    def test_bad_arguments(self):
        for args, word in (({}, "ArgumentsBad missing op"),
                           ({"op": "show"}, "OpUnknown"),
                           ({"op": "clear"}, "OpUnknown"),
                           ({"op": "set"}, "set needs text"),
                           ({"op": "set", "text": "  "}, "set needs text"),
                           ({"op": "set", "text": "x", "limit": 0}, "limit must be"),
                           ({"op": "done"}, "done needs reason"),
                           ({"op": "done", "reason": "r", "status": "failed"}, "ArgumentsBad"),
                           ({"op": "pause"}, "pause needs reason"),
                           ({"op": "get", "text": "x"}, "does not take text"),
                           ({"op": "resume", "reason": "x"}, "does not take reason")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout, args)
            self.assertTrue(r.stdout.startswith("goal: error: "), r.stdout)
        self.assertEqual(self.calls(), [])                              # nothing was run

    def test_lower_error_becomes_mine(self):
        r = self.run_tool({"op": "resume"}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "goal: error: GoalMissing bob has no goal (set one with aos-agent goal set TEXT)\n")
        self.assertIn("aos-agent: error: GoalMissing", r.stderr)


if __name__ == "__main__":
    unittest.main()
