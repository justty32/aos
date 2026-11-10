"""Test self_hook builds the aos-agent hook command line for each op and checks its arguments, with a fake aos-agent."""
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
elif "ls" in sys.argv:
    print('[{"name": "guard"}]')
elif os.environ.get("FAKE_FAIL") and "add" in sys.argv:
    sys.stderr.write("aos-agent: error: HookExists bob already has a hook named guard (add --replace to replace it)\n")
    sys.exit(1)
'''


class SelfHook(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="self-hook-"))
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

    def test_add_with_every_key(self):
        r = self.run_tool({"op": "add", "event": "before_tool", "path": "hooks/guard", "name": "g", "condition": ["a", "b"],
                           "intercept": False, "async": False, "on_error": "continue", "timeout_ms": 500, "replace": True})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(takes effect from the next event)", r.stdout)
        self.assertEqual(self.calls()[-1], [str(self.ws), "hook", "--target", "bob", "add", "--event", "before_tool", "--name", "g",
                                            "--condition", "a", "--condition", "b", "--no-intercept", "--on-error", "continue",
                                            "--timeout-ms", "500", "--replace", "hooks/guard"])

    def test_each_op(self):
        d = {"$env": "AOS_HOME", "$path": "/lib/x"}
        for args, want in (({"op": "ls"}, ["ls", "--json"]),
                           ({"op": "ls", "long": True}, ["ls", "-l"]),
                           ({"op": "get", "name": "guard"}, ["get", "guard"]),
                           ({"op": "add", "event": "after_queue", "path": "/abs/h", "async": True}, ["add", "--event", "after_queue", "--async", "/abs/h"]),
                           ({"op": "add", "event": "brain_failed", "condition": "ReplyBad", "name": "p", "path_json": d},
                            ["add", "--event", "brain_failed", "--name", "p", "--condition", "ReplyBad", "--path-json", json.dumps(d)]),
                           ({"op": "rm", "name": "guard"}, ["rm", "guard"]),
                           ({"op": "reset"}, ["reset", "-y"])):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            self.assertEqual(self.calls()[-1][1:], ["hook", "--target", "bob"] + want, args)
            self.assertEqual(self.calls()[-1][0], str(self.ws))

    def test_bad_arguments(self):
        for args, word in (({"op": "add", "event": "after_tool", "path": "h", "envs": {}}, "ArgumentsBad unknown key envs"),
                           ({"op": "add", "path": "h"}, "event needs"),
                           ({"op": "add", "event": "after_tool"}, "path"),
                           ({"op": "add", "event": "after_tool", "path": "h", "path_json": "x"}, "not both"),
                           ({"op": "add", "event": "after_tool", "path": "h", "condition": [1]}, "ArgumentsBad"),
                           ({"op": "rm", "name": "g", "replace": True}, "does not take replace"),
                           ({"op": "get"}, "name needs"),
                           ({"op": "nope"}, "OpUnknown")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout, args)
        self.assertEqual([c for c in self.calls() if c[1:2] == ["hook"]], [])

    def test_lower_error_passed_up(self):
        r = self.run_tool({"op": "add", "event": "after_tool", "path": "h"}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("self_hook: error: HookExists", r.stdout)
        self.assertIn("aos-agent: error: HookExists", r.stderr)


if __name__ == "__main__":
    unittest.main()
