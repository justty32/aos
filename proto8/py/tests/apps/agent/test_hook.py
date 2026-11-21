"""Test aos-agent hook on a fake daemon table: add writes only the agent's own hookeds copy (flags, path forms, --path-json), HookExists / --replace, rm (null vs delete), reset, ls / ls -l / --json / get, and the errors."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import env_helper  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
BIN = REPO / "proto8" / "bin" / "aos-agent"


def clean_env(**extra):
    return env_helper.clean_env(drop=("TC_",), **extra)


class Hook(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-hook-"))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"entry": "body.json"}, "hookeds": "hookeds.json"}))
        self.mine = self.defn / "hookeds.json"
        self.mine.write_text(json.dumps({"description": "test", "audit": {"event": "after_tool", "handler": "audit.sh", "condition": ["a", "b"]}}))
        (self.tmp / "h").mkdir()
        (self.tmp / "h" / "guard").write_text("#!/bin/sh\nexit 0\n")
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"bob": {
            "phase": "stopped", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))
        self.own = self.stack / "hookeds.json"

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
        return json.loads(self.own.read_text())

    def test_add_every_flag_relative(self):
        before = self.mine.read_bytes()
        r = self.agent("add", "--event", "before_tool", "--condition", "x", "--condition", "y",
                       "--timeout-ms", "500", "h/guard")
        self.assertIn("created %s" % self.own, r.stderr)
        self.assertEqual(self.own_hooks(), {"guard": {"event": "before_tool", "handler": os.path.relpath(self.tmp / "h" / "guard", self.stack),
                                                      "condition": ["x", "y"], "timeout_ms": 500}})
        self.assertEqual(self.mine.read_bytes(), before)

    def test_add_minimal_absolute_no_wait_and_folder_name(self):
        self.agent("add", "--event", "after_queue", str(self.tmp / "h") + "/")
        self.assertEqual(self.own_hooks(), {"h": {"event": "after_queue", "handler": str(self.tmp / "h")}})
        self.agent("add", "--event", "brain_failed", "--condition", "ReplyBad", "-n", "g2", "h/guard")
        self.assertEqual(self.own_hooks()["g2"]["condition"], "ReplyBad")

    def test_add_on_clock_and_start_stop(self):   # 11-11 clock-hook：on_clock 的三個旗標、ls -l 的 CONDITION 欄、起停事件
        self.agent("add", "--event", "on_clock", "--every-ms", "300000", "--clock", "_clock", "-n", "timer", "h/guard")
        self.assertEqual(self.own_hooks()["timer"], {"event": "on_clock", "handler": os.path.relpath(self.tmp / "h" / "guard", self.stack),
                                                     "every_ms": 300000, "clock": "_clock"})
        self.agent("add", "--event", "on_clock", "--every-cycles", "10", "-n", "c10", "h/guard")
        self.assertEqual(self.own_hooks()["c10"]["every_cycles"], 10)
        rows = {l.split("\t")[0]: l.split("\t") for l in self.agent("ls", "-l").stdout.splitlines()}
        self.assertEqual(rows["timer"][3], "clock=_clock,every_ms=300000")
        self.agent("add", "--event", "after_start", "-n", "up", "h/guard")
        self.agent("add", "--event", "after_stop", "-n", "down", "h/guard")
        self.assertEqual(self.own_hooks()["down"]["event"], "after_stop")
        self.fails("ArgumentsBad", "add", "--event", "on_clock", "-n", "x", "h/guard")                 # 沒給條件
        self.fails("ArgumentsBad", "add", "--event", "on_clock", "--every-ms", "0", "-n", "x", "h/guard")
        self.fails("ArgumentsBad", "add", "--event", "after_tool", "--every-ms", "5", "-n", "x", "h/guard")

    def test_add_on_clock_config(self):   # 11-16 ok-small：--config 原樣寫進格（任意 JSON），ls -l 的 CONDITION 欄看得到，只收 on_clock
        cfg = {"percent": 50, "wrap": True, "window": 200000}
        self.agent("add", "--event", "on_clock", "--every-ms", "5000", "--config", json.dumps(cfg), "-n", "cw", "h/guard")
        self.assertEqual(self.own_hooks()["cw"]["config"], cfg)
        self.agent("add", "--event", "on_clock", "--every-ms", "5000", "--config", "[1, \"a\"]", "--replace", "-n", "cw", "h/guard")
        self.assertEqual(self.own_hooks()["cw"]["config"], [1, "a"])
        rows = {l.split("\t")[0]: l.split("\t") for l in self.agent("ls", "-l").stdout.splitlines()}
        self.assertEqual(rows["cw"][3], 'every_ms=5000,config=[1,"a"]')
        self.agent("add", "--event", "on_clock", "--every-ms", "5000", "--replace", "-n", "cw", "h/guard")
        self.assertNotIn("config", self.own_hooks()["cw"])                                            # 沒給＝不帶（replace 不留舊的）
        self.assertIn("not JSON", self.fails("ArgumentsBad", "add", "--event", "on_clock", "--every-ms", "5", "--config", "{x",
                                             "-n", "x", "h/guard").stderr)
        self.assertIn("only for event on_clock", self.fails("ArgumentsBad", "add", "--event", "after_tool", "--config", "{}",
                                                            "-n", "x", "h/guard").stderr)
        self.assertIn("not standard JSON", self.fails("ArgumentsBad", "add", "--event", "on_clock", "--every-ms", "5", "--config", "NaN",
                                                      "-n", "x", "h/guard").stderr)
        self.agent("add", "--event", "on_clock", "--every-ms", "5", "--config", "-1", "-n", "neg", "h/guard")
        self.assertEqual(self.own_hooks()["neg"]["config"], -1)
        self.agent("add", "--event", "on_clock", "--every-ms", "5", "--config", json.dumps("a\tb"), "-n", "s", "h/guard")
        rows = {l.split("\t")[0]: l.split("\t") for l in self.agent("ls", "-l").stdout.splitlines()}
        self.assertEqual(rows["s"][3], 'every_ms=5,config="a\\tb"')                                   # quoted, tab escaped

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
        self.assertEqual(rows, [["audit", "null"] + ["-"] * 3 + [str(self.own)]])
        self.fails("HookMissing", "rm", "audit")

    def test_reset(self):
        self.agent("rm", "audit")
        r = self.agent("reset", "-y")
        self.assertIn("deleted", r.stdout)
        self.assertFalse(self.own.exists())
        self.assertIn("there was no copy", self.agent("reset", "-y").stdout)
        self.assertEqual(self.agent("ls").stdout, "audit\tafter_tool\taudit.sh\n")

    def test_ls_long_json_get(self):
        d = {"$env": "AOS_HOME", "$path": "/lib/x"}
        self.agent("add", "--event", "tool_added", "-n", "pj", "--path-json", json.dumps(d))
        self.assertEqual(self.agent().stdout, 'audit\tafter_tool\taudit.sh\npj\ttool_added\t{"$env":"AOS_HOME","$path":"/lib/x"}\n')
        rows = [l.split("\t") for l in self.agent("ls", "--long").stdout.splitlines()]
        self.assertEqual(rows[0], ["audit", "after_tool", "audit.sh", "a,b", "60000", str(self.mine)])
        self.assertEqual(rows[1][3], "-")
        got = json.loads(self.agent("ls", "-j").stdout)
        self.assertEqual(got[0], {"name": "audit", "event": "after_tool", "handler": "audit.sh", "condition": ["a", "b"],
                                  "from": str(self.mine)})
        self.assertEqual(json.loads(self.agent("get", "pj").stdout)["handler"], d)
        self.fails("HookMissing", "get", "nope")

    def test_bad_arguments(self):
        self.fails("FlagUnknown", "add", "--event", "after_queue", "--change", "h/guard")   # --change is gone (on by default)
        for gone in (("--no-intercept",), ("--async",), ("--on-error", "continue")):      # gone with the fourth layer (11-21)
            self.fails("FlagUnknown", "add", "--event", "after_tool", *gone, "h/guard")
        for args in (("add", "--event", "after_tool", "--timeout-ms", "x", "h/guard"),   # 0 is allowed now (= no limit)
                     ("add", "--event", "after_tool", "--every-ms", "5", "h/guard"),
                     ("add", "h/guard")):                                          # no --event
            p = self.fails("ArgumentsBad", *args)
            self.assertIn("(usage: ", p.stderr, args)
        self.assertFalse(self.own.exists())
        p = self.fails("PathMissing", "add", "--event", "after_tool", "h/nothing")
        self.assertIn("h/nothing does not exist (relative to the current directory)", p.stderr)   # 11-12 線 errpath：不印 cwd 的絕對路徑
        self.assertNotIn(str(self.tmp), p.stderr)
        self.fails("NameBad", "add", "--event", "after_tool", "-n", ".x", "h/guard")
        self.fails("FlagUnknown", "add", "--wait", "h/guard")
        self.fails("CommandUnknown", "nope")

    def test_flags_after_xxx(self):
        """11-10 cli-sweep Q1（使用者「1.收。」）：XXX 後的旗標也收，跟寫在前面一樣。"""
        self.agent("add", "h/guard", "--event", "after_tool", "--timeout-ms", "700")
        self.assertEqual(json.loads(self.own.read_text())["guard"]["timeout_ms"], 700)

    def test_missing_and_bad_list(self):
        self.own.write_text("{not json")
        self.fails("HooksBad", "ls")
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}}))
        r = self.fails("HooksMissing", "ls")
        self.assertIn('"hookeds": "hookeds.json"', r.stderr)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"hooks": "hooks.json"}}))   # the old place is not read
        self.fails("HooksMissing", "ls")
        (self.defn / "interfaces.json").write_text(json.dumps({"hookeds": [str(self.mine)]}))
        self.assertIn("no hookeds file it can keep a copy of", self.fails("HooksMissing", "ls").stderr)   # only an absolute one

    def test_any_event_name_is_taken(self):
        """11-21: event names are not checked (a declaration is only for reading); condition is kept on any event."""
        self.agent("add", "--event", "nope", "-n", "n1", "h/guard")
        self.agent("add", "--event", "before_queue", "--condition", "x", "-n", "n2", "h/guard")
        self.assertEqual((self.own_hooks()["n1"]["event"], self.own_hooks()["n2"]["condition"]), ("nope", "x"))
        self.assertNotIn("warning", self.agent("add", "--event", "before_compact", "-n", "n3", "h/guard").stderr)


if __name__ == "__main__":
    unittest.main()
