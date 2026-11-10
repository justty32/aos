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
    f.write(json.dumps(sys.argv[1:]) + "\n")
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

    def test_add_with_replace_envs_env_file(self):
        r = self.run_tool({"op": "add", "name": "math", "path": "tools/math", "replace": True,
                           "envs": {"B": "2", "A": "x y"}, "env_file": "secrets/m.env"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("added math", r.stdout)
        self.assertEqual(self.calls()[-1], ["tools", "--target", "bob", "add", "--name", "math", "--replace", "--envs", "A=x y",
                                            "--envs", "B=2", "--env-file", str(self.ws / "secrets" / "m.env"),
                                            str(self.ws / "tools" / "math")])

    def test_plain_add_rm_ls(self):
        self.assertEqual(self.run_tool({"op": "add", "name": "math", "path": "tools/math"}).returncode, 0)
        self.assertEqual(self.calls()[-1], ["tools", "--target", "bob", "add", "--name", "math", str(self.ws / "tools" / "math")])
        self.assertEqual(self.run_tool({"op": "rm", "name": "math"}).returncode, 0)
        self.assertEqual(self.calls()[-1], ["tools", "--target", "bob", "rm", "math"])
        r = self.run_tool({"op": "ls"})
        self.assertEqual(json.loads(r.stdout), [{"name": "math"}])

    def test_bad_arguments(self):
        for args, word in (({"op": "add", "name": "m", "path": "tools/math", "override": True}, "unknown argument override"),
                           ({"op": "add", "name": "m", "path": "tools/math", "envs": {"A": 1}}, "envs must be"),
                           ({"op": "rm", "name": "m", "replace": True}, "only go with op add"),
                           ({"op": "add", "name": "m", "path": "tools/math", "env_file": "/etc/passwd"}, "PathBad")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout)
        self.assertEqual([c for c in self.calls() if c[:1] == ["tools"]], [])

    def test_lower_error_passed_up(self):
        r = self.run_tool({"op": "add", "name": "math", "path": "tools/math"}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("self_tools: error: ToolExists", r.stdout)


if __name__ == "__main__":
    unittest.main()
