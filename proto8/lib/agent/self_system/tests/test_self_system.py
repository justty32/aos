"""Test self_system builds the aos-agent system command line (get, set, reset), hands set's text on stdin and checks its arguments, with a fake aos-agent."""
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
    sys.stderr.write("aos-agent: error: SystemMissing bob does not declare system\n")
    sys.exit(1)
elif sys.argv[-1] == "-":
    sys.stderr.write("aos-agent: warning: the screen of bob is open: it keeps the old text until it is opened again\n")
    print("set the system text of bob: /s/system.txt (%d bytes)" % len(data))
else:
    print("You are bob.")
'''


class SelfSystem(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="self-system-"))
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
        for args, want in (({"op": "get"}, ["get"]),
                           ({"op": "get", "long": True}, ["get", "-l"]),
                           ({"op": "set", "text": "Be short.\n"}, ["set", "-"]),
                           ({"op": "set", "text": ""}, ["set", "-"]),
                           ({"op": "reset"}, ["reset", "-y"])):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            call = self.calls()[-1]
            self.assertEqual(call[2:], ["system", "--target", "bob"] + want, args)
            self.assertEqual(call[0], str(self.ws))
            if args["op"] == "set":
                self.assertEqual(call[1], args["text"])
        self.assertIn("next brain call", r.stdout)

    def test_get_prints_text(self):
        r = self.run_tool({"op": "get"})
        self.assertEqual(r.stdout, "You are bob.\n")

    def test_warning_reaches_the_brain(self):
        r = self.run_tool({"op": "set", "text": "x"})
        self.assertIn("(the screen of bob is open", r.stdout)

    def test_bad_arguments(self):
        for args, word in (({"op": "set"}, "set needs text"),
                           ({"op": "set", "text": 3}, "ArgumentsBad text must be string"),
                           ({"op": "show"}, "OpUnknown"),
                           ({"op": "get", "text": "x"}, "does not take text"),
                           ({"op": "reset", "long": True}, "does not take long"),
                           ({}, "missing op")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout, args)
        self.assertEqual([c for c in self.calls() if c[2:3] == ["system"]], [])

    def test_lower_error_passed_up(self):
        r = self.run_tool({"op": "get"}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("self_system: error: SystemMissing bob does not declare system", r.stdout)


if __name__ == "__main__":
    unittest.main()
