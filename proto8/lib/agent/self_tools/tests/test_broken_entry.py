"""Test self_tools still works when one of the agent's registered tools points nowhere: ls marks it broken, get keeps its PathMissing, rm then add fixes it (real aos-agent and aos-tools, fake daemon table; 11-12 tool-path-broken)."""
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
PROTO = Path(__file__).resolve().parents[4]
CLOCK = PROTO / "lib" / "base" / "peek_now_time"


class BrokenEntry(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="self-tools-broken-"))
        d, defn, self.ws = self.tmp / "d", self.tmp / "defs" / "bob", self.tmp / "ws"
        (d / "procs" / "bob").mkdir(parents=True)
        defn.mkdir(parents=True)
        shutil.copytree(CLOCK, defn / "lib" / "clock")
        shutil.copytree(CLOCK, self.ws / "tools" / "aos_cache")
        (defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json"}}))
        (defn / "tools.json").write_text(json.dumps({"tools": {"clock": {"path": "lib/clock"}}}))
        (d / "procs_state.json").write_text(json.dumps({"procs": {"bob": {
            "phase": "running", "stack": "procs/bob", "ws": "../ws", "def": str(defn)}}}))
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        env["PATH"] = os.pathsep.join([str(PROTO / "cmd" / "aos-agent" / "bin"), str(PROTO / "cmd" / "aos-tools" / "bin"),
                                       os.path.expanduser("~/.local/bin"), env["PATH"]])
        self.env = dict(env, AOS_DAEMON=str(d), AOS_WS=str(self.ws),
                        AOS_STACK=str(d / "procs" / "bob" / "tools" / "self_tools") + "/", PYTHONDONTWRITEBYTECODE="1")
        self.ok({"op": "add", "path": "tools/aos_cache"})
        (self.ws / "new_tools").mkdir()
        (self.ws / "tools" / "aos_cache").rename(self.ws / "new_tools" / "aos_cache")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, args):
        return subprocess.run([sys.executable, str(TOOL)], input=json.dumps(args), capture_output=True, text=True,
                              env=self.env, timeout=60)

    def ok(self, args):
        r = self.run_tool(args)
        self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
        return r

    def test_ls_marks_broken_and_rm_add_fix_it(self):
        r = self.ok({"op": "ls"})
        self.assertIn("aos_cache\tbroken: PathMissing", r.stdout)
        self.assertIn("clock\tGet the current UTC time", r.stdout)
        self.assertIn("\tbroken\t", self.ok({"op": "ls", "long": True}).stdout)
        r = self.run_tool({"op": "get", "name": "aos_cache"})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith("self_tools: error: PathMissing tool aos_cache"), r.stdout)
        self.assertIn("removed aos_cache", self.ok({"op": "rm", "name": "aos_cache"}).stdout)
        self.ok({"op": "add", "path": "new_tools/aos_cache"})
        r = self.ok({"op": "ls"})
        self.assertNotIn("broken", r.stdout)
        self.assertIn("aos_cache\tGet the current UTC time", r.stdout)


if __name__ == "__main__":
    unittest.main()
