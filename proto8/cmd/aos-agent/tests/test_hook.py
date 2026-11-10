"""Test aos-agent hook on a fake daemon table: add writes only the agent's own hooks list (flags, path forms, --path-json), HookExists / --replace, rm (null vs delete), reset, ls / ls -l / --json / get, and the errors."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
BIN = REPO / "proto8" / "cmd" / "aos-agent" / "bin" / "aos-agent"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and not k.startswith("TC_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


class Hook(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-hook-"))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"hooks": "hooks.json"}}))
        self.mine = self.defn / "hooks.json"
        self.mine.write_text(json.dumps({"hooks": {"audit": {"event": "after_tool", "handler": "audit.sh", "condition": ["a", "b"]}}}))
        (self.tmp / "h").mkdir()
        (self.tmp / "h" / "guard").write_text("#!/bin/sh\nexit 0\n")
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"bob": {
            "phase": "stopped", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))
        self.own = self.stack / "hooks.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def agent(self, *args, ok=True):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "hook", "--target", "bob", *[str(a) for a in args]],
                           env=clean_env(), capture_output=True, text=True, timeout=60, cwd=self.tmp, stdin=subprocess.DEVNULL)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def fails(self, code, *args):
        p = self.agent(*args, ok=False)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("aos-agent: error: %s" % code, p.stderr)
        return p

    def own_hooks(self):
        return json.loads(self.own.read_text())["hooks"]

    def test_add_every_flag_relative(self):
        before = self.mine.read_bytes()
        r = self.agent("add", "--event", "before_tool", "--condition", "x", "--condition", "y", "--no-intercept", "--on-error", "continue",
                       "--timeout-ms", "500", "h/guard")
        self.assertIn("created %s" % self.own, r.stderr)
        self.assertEqual(self.own_hooks(), {"guard": {"event": "before_tool", "handler": os.path.relpath(self.tmp / "h" / "guard", self.stack),
                                                      "condition": ["x", "y"], "intercept": False, "on_error": "continue", "timeout_ms": 500}})
        self.assertEqual(self.mine.read_bytes(), before)

    def test_add_minimal_absolute_no_wait_and_folder_name(self):
        self.agent("add", "--event", "after_queue", "--async", str(self.tmp / "h") + "/")
        self.assertEqual(self.own_hooks(), {"h": {"event": "after_queue", "handler": str(self.tmp / "h"), "async": True}})
        self.agent("add", "--event", "brain_failed", "--condition", "ReplyBad", "-n", "g2", "h/guard")
        self.assertEqual(self.own_hooks()["g2"]["condition"], "ReplyBad")

    def test_path_json(self):
        d = {"$env": "AOS_HOME", "$path": "/lib/x"}
        self.agent("add", "--event", "tool_added", "--name", "pj", "--path-json", json.dumps(d))
        self.assertEqual(self.own_hooks()["pj"], {"event": "tool_added", "handler": d})
        self.fails("ArgumentsBad", "add", "--event", "tool_added", "--path-json", json.dumps(d))       # needs --name
        self.fails("ArgumentsBad", "add", "--event", "tool_added", "-n", "q", "--path-json", "[1]")

    def test_exists_and_replace(self):
        r = self.fails("HookExists", "add", "--event", "after_tool", "--name", "audit", "h/guard")
        self.assertIn("--replace", r.stderr)
        self.assertFalse(self.own.exists())
        self.agent("add", "--event", "after_tool", "--name", "audit", "--replace", "h/guard")
        self.assertEqual(json.loads(self.agent("get", "audit").stdout)["from"], str(self.own))

    def test_rm_definition_hook_is_null_and_own_is_deleted(self):
        self.agent("add", "--event", "before_queue", "h/guard")
        self.agent("rm", "guard")
        self.assertEqual(self.own_hooks(), {})
        self.agent("rm", "audit")
        self.assertEqual(self.own_hooks(), {"audit": None})
        self.assertEqual(self.agent("ls").stdout, "")
        rows = [l.split("\t") for l in self.agent("ls", "-l").stdout.splitlines()]
        self.assertEqual(rows, [["audit", "null"] + ["-"] * 6 + [str(self.own)]])
        self.fails("HookMissing", "rm", "audit")

    def test_reset(self):
        self.agent("rm", "audit")
        r = self.agent("reset", "-y")
        self.assertIn("deleted", r.stdout)
        self.assertFalse(self.own.exists())
        self.assertIn("there was no file", self.agent("reset", "-y").stdout)
        self.assertEqual(self.agent("ls").stdout, "audit\tafter_tool\taudit.sh\n")

    def test_ls_long_json_get(self):
        d = {"$env": "AOS_HOME", "$path": "/lib/x"}
        self.agent("add", "--event", "tool_added", "-n", "pj", "--path-json", json.dumps(d))
        self.assertEqual(self.agent().stdout, 'audit\tafter_tool\taudit.sh\npj\ttool_added\t{"$env":"AOS_HOME","$path":"/lib/x"}\n')
        rows = [l.split("\t") for l in self.agent("ls", "--long").stdout.splitlines()]
        self.assertEqual(rows[0], ["audit", "after_tool", "audit.sh", "a,b", "false", "stop", "true", "60000", str(self.mine)])
        self.assertEqual(rows[1][3], "-")
        got = json.loads(self.agent("ls", "-j").stdout)
        self.assertEqual(got[0], {"name": "audit", "event": "after_tool", "handler": "audit.sh", "condition": ["a", "b"], "intercept": True,
                                  "async": False, "on_error": "stop", "timeout_ms": 60000, "from": str(self.mine)})
        self.assertEqual(json.loads(self.agent("get", "pj").stdout)["handler"], d)
        self.fails("HookMissing", "get", "nope")

    def test_bad_arguments(self):
        self.fails("FlagUnknown", "add", "--event", "after_queue", "--change", "h/guard")   # --change is gone (on by default)
        for args in (("add", "--event", "nope", "h/guard"),
                     ("add", "--event", "before_queue", "--condition", "x", "h/guard"),
                     ("add", "--event", "after_tool", "--timeout-ms", "0", "h/guard"),
                     ("add", "--event", "after_tool", "--on-error", "maybe", "h/guard"),
                     ("add", "h/guard")):                                          # no --on
            p = self.fails("ArgumentsBad", *args)
            self.assertIn("(usage: ", p.stderr, args)
        self.assertFalse(self.own.exists())
        self.fails("PathMissing", "add", "--event", "after_tool", "h/nothing")
        self.fails("NameBad", "add", "--event", "after_tool", "-n", ".x", "h/guard")
        self.fails("FlagUnknown", "add", "--wait", "h/guard")
        self.fails("CommandUnknown", "nope")

    def test_flags_after_xxx(self):
        """11-10 cli-sweep Q1（使用者「1.收。」）：XXX 後的旗標也收，跟寫在前面一樣。"""
        self.agent("add", "h/guard", "--event", "after_tool", "--no-intercept")
        self.assertEqual(json.loads(self.own.read_text())["hooks"]["guard"]["intercept"], False)

    def test_missing_and_bad_list(self):
        self.own.write_text("{not json")
        self.fails("HooksBad", "ls")
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}}))
        r = self.fails("HooksMissing", "ls")
        self.assertIn('{"aos-agent": {"hooks": "hooks.json"}}', r.stderr)


if __name__ == "__main__":
    unittest.main()
