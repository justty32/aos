"""Test agents_ctl turns each op into the matching aos-agent ctl command line (one key = one flag), rejects unknown keys and passes lower errors up, with a fake aos-agent."""
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
NAME = TOOL.parent.name

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps([os.getcwd()] + sys.argv[1:]) + "\n")
if os.environ.get("FAKE_FAIL"):
    sys.stderr.write("aos-agent: error: InstanceMissing no agent named kid\n")
    sys.exit(1)
print("out of " + " ".join(sys.argv[1:3]))
'''


class AgentsCtl(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agents-ctl-"))
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "aos-agent").write_text(FAKE)
        (bin_ / "aos-agent").chmod(0o755)
        self.log = self.tmp / "log"
        self.env = dict(os.environ, PATH="%s:%s" % (bin_, os.environ["PATH"]), AOS_WS=str(self.ws), AOS_DAEMON=str(self.tmp / "d"),
                        AOS_STACK=str(self.tmp / "st"), FAKE_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, args, **env):
        return subprocess.run([str(TOOL)], input=json.dumps(args), capture_output=True, text=True, env=dict(self.env, **env), timeout=30)

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_each_op(self):
        d = {"$env": "AOS_HOME", "$path": "/templates/agent-fsm"}
        for args, want in (
                ({"op": "add", "def": "defs/helper"}, ["add", "defs/helper"]),
                ({"op": "add", "def": "defs/helper", "name": "w", "ws": "work", "stack": "/s/w", "limits": {"mem_mb": 512},
                  "envs": {"B": "2", "A": "x y"}, "auto_restart": True, "timeout_s": 5, "on_queued": "ok"},
                 ["add", "--name", "w", "--ws", "work", "--stack", "/s/w", "--limits", '{"mem_mb": 512}', "--envs", "A=x y",
                  "--envs", "B=2", "--auto-restart", "--timeout-s", "5", "--on-queued", "ok", "defs/helper"]),
                ({"op": "add", "def_json": d, "name": "w", "ws_json": {"$env": "PROJ"}, "stack_json": "st/w"},
                 ["add", "--name", "w", "--ws-json", '{"$env": "PROJ"}', "--stack-json", '"st/w"', "--path-json", json.dumps(d)]),
                ({"op": "rm", "name": "w"}, ["rm", "w"]),
                ({"op": "rm", "name": "w", "purge": True, "timeout_s": 2.5}, ["rm", "--purge", "-y", "--timeout-s", "2.5", "w"]),
                ({"op": "ls"}, ["ls", "--json"]),
                ({"op": "ls", "long": True}, ["ls", "-l"]),
                ({"op": "state", "name": "w"}, ["state", "--target", "w"]),
                ({"op": "where", "name": "w"}, ["where", "--target", "w"]),
                ({"op": "where", "name": "w", "what": "ws"}, ["where", "--target", "w", "--ws"]),
                ({"op": "who"}, ["who", "--json"]),
                ({"op": "who", "stack": "/s/w/tools/x"}, ["who", "--json", "--stack", "/s/w/tools/x"]),
                ({"op": "stop", "name": "w", "timeout_s": 3}, ["stop", "--target", "w", "--timeout-s", "3"]),
                ({"op": "sleep", "name": "w"}, ["sleep", "--target", "w"]),
                ({"op": "start", "name": "w", "on_queued": "ok"}, ["start", "--target", "w", "--on-queued", "ok"]),
                ({"op": "wake", "name": "w"}, ["wake", "--target", "w"]),
                ({"op": "pause", "name": "w"}, ["pause", "--target", "w"]),
                ({"op": "resume", "name": "w"}, ["resume", "--target", "w"])):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            self.assertEqual(self.calls()[-1], [str(self.ws), "ctl"] + want, args)
            self.assertIn("out of ctl", r.stdout)

    def test_ws_created(self):
        r = self.run_tool({"op": "add", "def": "defs/helper", "ws": "new/ws"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.ws / "new" / "ws").is_dir())

    def test_bad_arguments_send_nothing(self):
        for args, word in (({"op": "add", "def": "d", "llm": {"model": "fake"}}, "unknown key llm"),
                           ({"op": "rm", "name": "w", "long": True}, "op rm does not take long"),
                           ({"op": "pause", "name": "w", "timeout_s": 3}, "op pause does not take timeout_s"),
                           ({"op": "add"}, "def"),
                           ({"op": "add", "def": "d", "def_json": "d"}, "not both"),
                           ({"op": "add", "def": {"$env": "AOS_HOME"}}, "def must be string"),
                           ({"op": "add", "def": "d", "ws": "a", "ws_json": "a"}, "not both"),
                           ({"op": "add", "def": "d", "envs": {"A": 1}}, "envs must be"),
                           ({"op": "stop", "name": "w", "timeout_s": 0}, "timeout_s must be"),
                           ({"op": "state"}, "name needs"),
                           ({"op": "where", "name": "w", "what": "def"}, "ArgumentsBad"),
                           ({"op": "say", "name": "w"}, "OpUnknown"),
                           ({}, "ArgumentsBad")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(NAME + ": error: ", r.stdout, args)
            self.assertIn(word, r.stdout, args)
        self.assertEqual(self.calls(), [])

    def test_lower_error_passed_up(self):
        r = self.run_tool({"op": "state", "name": "kid"}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn(NAME + ": error: InstanceMissing no agent named kid", r.stdout)
        self.assertIn("aos-agent: error: InstanceMissing", r.stderr)


if __name__ == "__main__":
    unittest.main()
