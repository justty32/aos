"""Test self_tools builds the aos-agent tools command line (replace, envs, env_file) and checks its arguments, with a fake aos-agent."""
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
elif "ls" in sys.argv:
    print('[{"name": "math"}]')
elif os.environ.get("FAKE_FAIL") and "add" in sys.argv:
    sys.stderr.write("aos-agent: error: ToolExists math is already listed (use --replace)\n")
    sys.exit(1)
'''


class SelfTools(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="self-tools-"))
        self.ws = self.tmp / "ws"
        (self.ws / "tools" / "math").mkdir(parents=True)
        (self.ws / "secrets").mkdir()
        (self.ws / "secrets" / "m.env").write_text("K=1\n")
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

    def test_add_with_every_flag(self):
        r = self.run_tool({"op": "add", "name": "math", "path": "tools/math", "replace": True, "no_cache": True,
                           "envs": {"B": "2", "A": "x y"}, "env_file": "secrets/m.env"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("next turn", r.stdout)
        self.assertEqual(self.calls()[-1], [str(self.ws), "tools", "--target", "bob", "add", "--name", "math", "--replace",
                                            "--envs", "A=x y", "--envs", "B=2", "--env-file", "secrets/m.env", "--no-cache",
                                            "tools/math"])

    def test_each_op(self):
        d = {"$env": "AOS_HOME", "$path": "/lib/base/math"}
        for args, want in (({"op": "ls"}, ["ls", "-b"]),
                           ({"op": "ls", "long": True}, ["ls", "-l"]),
                           ({"op": "get", "name": "math"}, ["get", "math"]),
                           ({"op": "add", "path": "/anywhere/tool"}, ["add", "/anywhere/tool"]),
                           ({"op": "add", "path_json": d}, ["add", "--path-json", json.dumps(d)]),
                           ({"op": "rm", "name": "self_tools"}, ["rm", "self_tools"]),
                           ({"op": "reset"}, ["reset", "-y"])):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            self.assertEqual(self.calls()[-1][1:], ["tools", "--target", "bob"] + want, args)
            self.assertEqual(self.calls()[-1][0], str(self.ws))

    def test_bad_arguments(self):
        for args, word in (({"op": "add", "path": "tools/math", "override": True}, "ArgumentsBad unknown key override"),
                           ({"op": "add", "path": "tools/math", "envs": {"A": 1}}, "envs must be"),
                           ({"op": "rm", "name": "m", "replace": True}, "does not take replace"),
                           ({"op": "add"}, "path"),
                           ({"op": "add", "path": "a", "path_json": {"$env": "X"}}, "not both"),
                           ({"op": "get"}, "name needs"),
                           ({"op": "nope"}, "OpUnknown")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout, args)
        self.assertEqual([c for c in self.calls() if c[1:2] == ["tools"]], [])

    def test_lower_error_passed_up(self):
        r = self.run_tool({"op": "add", "name": "math", "path": "tools/math"}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("self_tools: error: ToolExists", r.stdout)


if __name__ == "__main__":
    unittest.main()
