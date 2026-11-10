"""Test self_llm builds the aos-agent llm command line (show, set, reset) and checks its arguments, with a fake aos-agent."""
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
    print("endpoint=fake")
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
        for args, want in (({"op": "show"}, ["show"]),
                           ({"op": "set", "settings": {"endpoint": "smart-high", "model": "m"}}, ["set", "endpoint=smart-high", "model=m"]),
                           ({"op": "reset"}, ["reset", "-y"])):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            self.assertEqual(self.calls()[-1][1:], ["llm", "--target", "bob"] + want, args)
        self.assertIn("next turn", r.stdout)

    def test_bad_arguments(self):
        for args, word in (({"op": "set"}, "set needs settings"),
                           ({"op": "set", "settings": {"endpoint": 3}}, "set needs settings"),
                           ({"op": "set", "settings": {"a=b": "c"}}, "set needs settings"),
                           ({"op": "show", "settings": {}}, "does not take settings"),
                           ({"op": "nope"}, "OpUnknown")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout, args)
        self.assertEqual([c for c in self.calls() if c[1:2] == ["llm"]], [])

    def test_lower_error_passed_up(self):
        r = self.run_tool({"op": "set", "settings": {"endpoint": "x"}}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("self_llm: error: LlmBad", r.stdout)


if __name__ == "__main__":
    unittest.main()
