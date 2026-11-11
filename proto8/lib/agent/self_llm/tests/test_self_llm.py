"""Test self_llm builds the aos-agent llm command line (ls, set, rm, reset) and checks its arguments, with a fake aos-agent."""
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
LIB = Path(__file__).resolve().parents[3]

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps([os.getcwd()] + sys.argv[1:]) + "\n")
if sys.argv[1:3] == ["ctl", "who"]:
    print("bob")
elif os.environ.get("FAKE_FAIL"):
    sys.stderr.write("aos-agent: error: LlmBad unknown endpoint x\n")
    sys.exit(1)
else:
    if "temp" in sys.argv[-1]:
        sys.stderr.write("aos-agent: warning: temp is not a setting the body of bob reads (it reads: model); stored anyway\n")
    print("model=fake")
'''


class SelfLlm(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="self-tools-"))
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
        for args, want in (({"op": "ls"}, ["ls"]),
                           ({"op": "ls", "long": True}, ["ls", "-l"]),
                           ({"op": "set", "settings": {"model": "smart-high", "temperature": "0.2"}}, ["set", "model=smart-high", "temperature=0.2"]),
                           ({"op": "rm", "keys": ["temperature", "top_p"]}, ["rm", "temperature", "top_p"]),
                           ({"op": "reset"}, ["reset", "-y"])):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            self.assertEqual(self.calls()[-1][1:], ["llm", "--target", "bob"] + want, args)
        self.assertIn("next brain call", r.stdout)

    def test_bad_arguments(self):
        for args, word in (({"op": "set"}, "set needs settings"),
                           ({"op": "set", "settings": {"model": 3}}, "set needs settings"),
                           ({"op": "rm"}, "rm needs keys"),
                           ({"op": "rm", "keys": []}, "rm needs keys"),
                           ({"op": "show"}, "OpUnknown"),
                           ({"op": "set", "settings": {"a=b": "c"}}, "set needs settings"),
                           ({"op": "ls", "settings": {}}, "does not take settings"),
                           ({"op": "set", "settings": {"system": "be nice"}}, "change your system text with self_system"),
                           ({"op": "nope"}, "OpUnknown")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout, args)
        self.assertEqual([c for c in self.calls() if c[1:2] == ["llm"]], [])

    def test_unread_key_warning_reaches_the_brain(self):
        r = self.run_tool({"op": "set", "settings": {"temp": "1"}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("temp is not a setting the body of bob reads", r.stdout)

    def test_lower_error_passed_up(self):
        r = self.run_tool({"op": "set", "settings": {"model": "x"}}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("self_llm: error: LlmBad", r.stdout)


if __name__ == "__main__":
    unittest.main()
