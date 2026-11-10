"""Test self_history builds the aos-agent history command line (ls, rm, summarize, set) and refuses the step in progress, with a fake aos-agent."""
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
elif sys.argv[4:] == ["ls", "--json"]:
    print(os.environ["FAKE_ROWS"])
elif sys.argv[4:] == ["ls"] and os.environ.get("FAKE_CUT"):
    print("(5 earlier messages not shown: lines 1-5; -a shows all, or give a RANGE)")
    print("6\tuser\tm6")
elif os.environ.get("FAKE_FAIL"):
    sys.stderr.write("aos-agent: error: RangeBad 9 is outside 1-5 (the history has 5 messages)\n")
    sys.exit(1)
else:
    print("done")
'''
CALL = {"role": "assistant", "content": "", "tool_calls": [{"id": "c9", "type": "function",
                                                             "function": {"name": "self_history", "arguments": "{}"}}]}
FSM = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}, {"role": "user", "content": "c"},
       CALL]                                                   # 這一步＝第 4 行（叫我的那則）
ECA = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"},
       {"role": "user", "content": "c"}, {"role": "user", "content": "d"}]   # 這一輪交進來的 user＝第 3 行起


def rows(msgs):
    return json.dumps([{"line": i, "message": m} for i, m in enumerate(msgs, 1)])


class SelfHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="self-history-"))
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "aos-agent").write_text(FAKE)
        (bin_ / "aos-agent").chmod(0o755)
        self.log = self.tmp / "log"
        self.env = dict(os.environ, PATH="%s:%s" % (bin_, os.environ["PATH"]), AOS_WS=str(self.ws),
                        AOS_STACK=str(self.tmp / "st"), FAKE_LOG=str(self.log), FAKE_ROWS=rows(FSM),
                        PYTHONDONTWRITEBYTECODE="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, args, **env):
        return subprocess.run([sys.executable, str(TOOL)], input=json.dumps(args), capture_output=True, text=True,
                              env=dict(self.env, **env), timeout=30)

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def last(self):
        return self.calls()[-1][1:]

    def test_each_op(self):
        base = ["history", "--target", "bob"]
        for args, want in (({"op": "ls"}, ["ls"]),
                           ({"op": "ls", "range": "2-3", "json": True}, ["ls", "--json", "2-3"]),
                           ({"op": "ls", "long": True}, ["ls", "--long"]),
                           ({"op": "ls", "all": True, "long": True}, ["ls", "--all", "--long"]),
                           ({"op": "rm", "range": 2}, ["rm", "--", "2"]),
                           ({"op": "rm", "range": "1-3", "keep": "old.jsonl"}, ["rm", "--keep", "old.jsonl", "--", "1-3"]),
                           ({"op": "summarize", "range": "1-2", "text": "-x", "role": "assistant", "no_keep": True},
                            ["summarize", "--no-keep", "-y", "--role", "assistant", "--", "1-2", "-x"]),
                           ({"op": "set", "line": 3, "message": {"role": "user", "content": "hi"}},
                            ["set", "--", "3", json.dumps({"role": "user", "content": "hi"})])):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
            self.assertEqual(self.last(), base + want, args)
            self.assertEqual(self.calls()[-1][0], str(self.ws))
        self.assertIn("next turn", r.stdout)

    def test_ls_says_which_lines_are_locked(self):
        r = self.run_tool({"op": "ls"})
        self.assertIn("(4 messages; lines 4-4 are the step in progress and cannot be changed)", r.stdout)
        r = self.run_tool({"op": "ls"}, FAKE_ROWS=rows(ECA))
        self.assertIn("lines 3-4 are the step in progress", r.stdout)

    def test_ls_note_names_my_keys(self):
        r = self.run_tool({"op": "ls"}, FAKE_CUT="1")
        self.assertEqual(r.stdout.splitlines()[0], '(5 earlier messages not shown: lines 1-5; "all": true shows all, or give a "range")')

    def test_step_in_progress_is_locked(self):
        for msgs, args in ((FSM, {"op": "rm", "range": "3-4"}), (FSM, {"op": "rm", "range": "2-"}),
                           (FSM, {"op": "set", "line": 4, "message": {"role": "user", "content": "x"}}),
                           (FSM, {"op": "summarize", "range": "4", "text": "x"}),
                           (ECA, {"op": "rm", "range": "3"})):
            before = len(self.calls())
            r = self.run_tool(args, FAKE_ROWS=rows(msgs))
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("self_history: error: RangeBad", r.stdout, args)
            self.assertIn("step in progress", r.stdout)
            self.assertEqual([c[4] for c in self.calls()[before:] if c[1] == "history"], ["ls"], args)   # 只看、沒改
        r = self.run_tool({"op": "rm", "range": "1-3"})
        self.assertEqual(r.returncode, 0, r.stdout)
        r = self.run_tool({"op": "rm", "range": "1-2"}, FAKE_ROWS=rows(ECA))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_bad_arguments(self):
        for args, word in (({"op": "rm"}, "range needs"), ({"op": "rm", "range": True}, "ArgumentsBad"),
                           ({"op": "summarize", "range": "1"}, "text needs"),
                           ({"op": "set", "line": 1, "message": "hi"}, "message must be"),
                           ({"op": "rm", "range": "1", "keep": "a", "no_keep": True}, "not both"),
                           ({"op": "ls", "text": "x"}, "does not take text"),
                           ({"op": "ls", "all": True, "range": "2-"}, "not both"),
                           ({"op": "nope"}, "OpUnknown"), ({}, "missing op")):
            r = self.run_tool(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn(word, r.stdout, args)
        self.assertEqual([c for c in self.calls() if c[1:2] == ["history"]], [])

    def test_lower_error_passed_up(self):
        r = self.run_tool({"op": "rm", "range": "1"}, FAKE_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("self_history: error: RangeBad 9 is outside", r.stdout)


if __name__ == "__main__":
    unittest.main()
