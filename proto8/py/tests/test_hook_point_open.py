"""Test aos.hook_point.open and its handle: where points and hooks come from, lists read again on every fire, the declared change types checked per hook inside the engine, the caller's check, names() and only, and fail() (raises as given, or FailReturned when it returns). Real aos-exec (env.sh on PATH)."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PY))
from aos import hook_point

POINTS = {"description": "a test provider", "provider": "saver", "points": {
    "before_save": {"when": "before a file is saved", "phase": "before",
                    "fields": {"file": "the file name", "who": "the user", "size": "bytes"},
                    "condition": "who", "change": {"file": "nonempty_string"}, "block": True, "if_blocked": "not saved"},
    "after_save": {"when": "after a file is saved", "phase": "after", "fields": {"file": "the file name", "meta": "extra"},
                   "change": {"meta": "object"}, "entry_keys": ["every_ms"]}}}


class Stop(Exception):
    def __init__(self, code, sentence):
        super().__init__(sentence)
        self.code = code


def die(code, sentence):
    raise Stop(code, sentence)


class Open(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="hook-point-open-")
        self.addCleanup(tmp.cleanup)
        self.d = Path(os.path.realpath(tmp.name))
        self.stack = str(self.d / "stack")
        self.points = self.d / "hook_points.json"
        self.points.write_text(json.dumps(POINTS))
        self.list = self.d / "hooks.json"
        self.hooks = {}
        self.warned = []

    def handler(self, name, body, event="before_save", **entry):
        p = self.d / ("h_" + name)
        p.write_text("#!/bin/sh\n" + body + "\n")
        p.chmod(0o755)
        self.hooks[name] = dict({"event": event, "handler": p.name}, **entry)
        self.list.write_text(json.dumps({"hooks": self.hooks}))

    def open(self, **kw):
        kw.setdefault("lists", [str(self.list)])
        return hook_point.open([str(self.points)], stack=self.stack, fail=die, warn=self.warned.append, **kw)

    def stopped(self, code, fn, *args, **kw):
        with self.assertRaises(Stop) as c:
            fn(*args, **kw)
        self.assertEqual(c.exception.code, code)
        return str(c.exception)

    def test_nobody_listens_and_the_shapes(self):
        h = self.open()
        self.assertEqual(set(h.points), {"before_save", "after_save"})
        self.assertEqual(h.table["before_save"], {"condition": "who", "intercept": ("file",), "block": True})
        self.assertEqual(h.fire("before_save", {"file": "a"}),
                         {"data": {"file": "a"}, "changed": [], "blocked": False, "hook": None, "text": ""})
        self.assertFalse(h.has("before_save"))
        self.assertEqual(h.names("before_save", {}), [])
        self.assertFalse((self.d / "stack").exists())          # no hook = no process, no folder

    def test_lists_are_read_again_on_every_fire(self):
        h = self.open()
        self.assertFalse(h.fire("before_save", {"file": "a"})["blocked"])
        self.handler("deny", "echo no; exit 10")              # written after open
        r = h.fire("before_save", {"file": "a"})
        self.assertEqual((r["blocked"], r["hook"], r["text"]), (True, "deny", "no\n"))
        self.hooks["deny"] = None                              # null turns it off
        self.list.write_text(json.dumps({"hooks": self.hooks}))
        self.assertFalse(h.fire("before_save", {"file": "a"})["blocked"])

    def test_change_keys_and_declared_types(self):
        self.handler("a_rename", "echo '{\"file\": \"b.txt\", \"size\": 9}'")
        r = self.open().fire("before_save", {"file": "a.txt", "size": 1})
        self.assertEqual((r["data"], r["changed"]), ({"file": "b.txt", "size": 1}, ["file"]))   # size: not a change key
        self.handler("a_rename", "echo '{\"file\": \"  \"}'")   # nonempty_string, declared
        why = self.stopped("HookFailed", self.open().fire, "before_save", {"file": "a.txt"})
        self.assertIn("file in stdout must be a non-empty string", why)
        self.handler("a_rename", "echo '{\"file\": \"\"}'", on_error="continue")
        self.handler("b_seen", "cat > \"$AOS_STACK/seen.json\"")
        r = self.open().fire("before_save", {"file": "a.txt"})
        self.assertEqual((r["data"]["file"], r["changed"]), ("a.txt", []))   # the bad value never got in
        seen = json.loads((self.d / "stack" / "hooks" / "b_seen" / "seen.json").read_text())
        self.assertEqual(seen["file"], "a.txt")                # and the next hook saw the original
        self.assertEqual(len(self.warned), 1)
        self.assertIn("on_error: continue", self.warned[0])
        self.handler("c_meta", "echo '{\"meta\": [1]}'", event="after_save")
        self.assertIn("meta in stdout must be a JSON object",
                      self.stopped("HookFailed", self.open().fire, "after_save", {"file": "a", "meta": {}}))

    def test_caller_check_runs_after_the_type_check(self):
        calls = []

        def mine(event, key, value):
            calls.append((event, key, value))
            if value == "secret.txt":
                raise ValueError("file in stdout must not be secret.txt")
        self.handler("a", "echo '{\"file\": \"secret.txt\"}'")
        why = self.stopped("HookFailed", self.open(check=mine).fire, "before_save", {"file": "x"})
        self.assertIn("must not be secret.txt", why)
        self.handler("a", "echo '{\"file\": \"\"}'")
        calls.clear()
        self.stopped("HookFailed", self.open(check=mine).fire, "before_save", {"file": "x"})
        self.assertEqual(calls, [])                            # the declared type failed first

    def test_condition_names_and_only(self):
        self.handler("a_alice", "exit 0", condition="alice")
        self.handler("b_any", "exit 0")
        self.handler("c_after", "exit 0", event="after_save")
        h = self.open()
        self.assertTrue(h.has("before_save"))
        self.assertEqual(h.names("before_save", {"who": "alice"}), ["a_alice", "b_any"])
        self.assertEqual(h.names("before_save", {"who": "bob"}), ["b_any"])
        self.handler("a_alice", "echo stopped; exit 10", condition="alice")
        r = h.fire("before_save", {"who": "bob"}, only=["a_alice", "c_after"])
        self.assertEqual(r["hook"], "a_alice")                 # only = these names, no condition compared again
        self.assertFalse(h.fire("before_save", {"who": "bob"})["blocked"])

    def test_entry_keys_and_entry_check(self):
        self.handler("a", "exit 0", every_ms=5)
        self.assertIn("every_ms is only for event after_save", self.stopped("HooksBad", self.open().load))
        self.hooks.clear()
        self.handler("a", "exit 0", event="after_save", every_ms=5)
        self.assertEqual(list(self.open().load()), ["a"])

        def positive(entry):
            if entry.get("every_ms", 1) <= 0:
                raise hook_point.hook_handle.hook_run.HooksBad("every_ms must be a positive integer")
        self.handler("a", "exit 0", event="after_save", every_ms=0)
        why = self.stopped("HooksBad", self.open(entry_check=positive).fire, "after_save", {})
        self.assertIn("hook a in %s: every_ms must be a positive integer" % self.list, why)
        self.handler("a", "exit 0", event="before_sav")
        self.assertIn("event must be one of", self.stopped("HooksBad", self.open().has, "before_save"))

    def test_entries_given_and_table_form(self):
        self.handler("deny", "exit 10")
        entries = hook_point.hook_handle.hook_lists.load([str(self.list)], hook_point.engine_table(hook_point.read([str(self.points)])))
        h = hook_point.open([str(self.points)], entries=entries, stack=self.stack, fail=die)
        self.assertTrue(h.fire("before_save", {})["blocked"])
        calls = []
        h = hook_point.open(hook_point.read([str(self.points)]), entries=lambda: calls.append(1) or entries,
                            stack=self.stack, fail=die)
        h.fire("before_save", {})
        h.fire("before_save", {})
        self.assertEqual(len(calls), 2)                        # a function = asked on every fire
        table = {"before_save": {"condition": None, "intercept": ("file",), "block": True}}
        h = hook_point.open(table=table, lists=[str(self.list)], stack=self.stack, fail=die)
        self.assertEqual(h.points, {})
        self.assertTrue(h.fire("before_save", {})["blocked"])
        self.handler("deny", "echo '{\"file\": \"\"}'")
        self.assertEqual(h.fire("before_save", {"file": "a"})["data"]["file"], "")   # a table has no declared types

    def test_errors_go_to_fail(self):
        self.assertIn("no hook point before_sav (points: before_save, after_save)",
                      self.stopped("EventUnknown", self.open().fire, "before_sav", {}))
        self.points.write_text(json.dumps({"provider": "x", "points": {"Bad": {}}}))
        self.assertIn("may only have a-z", self.stopped("PointsBad", self.open))
        self.list.write_text("{")
        h = hook_point.open({"p": {"when": "w", "phase": "on", "fields": {}}},   # read()'s shape, given directly
                            lists=[str(self.list)], stack=self.stack, fail=die)
        self.assertIn("cannot read", self.stopped("HooksBad", h.fire, "p", {}))

    def test_fail_that_returns(self):
        got = []
        h = hook_point.open([str(self.points)], lists=[str(self.list)], stack=self.stack,
                            fail=lambda code, sentence: got.append(code))
        with self.assertRaises(hook_point.FailReturned) as c:
            h.fire("nope", {})
        self.assertEqual((got, c.exception.code), (["EventUnknown"], "EventUnknown"))
        self.handler("bad", "exit 3")
        with self.assertRaises(hook_point.FailReturned) as c:
            h.fire("before_save", {})
        self.assertEqual(c.exception.code, "HookFailed")
        self.assertIn("hook bad (event before_save) failed: exited 3", str(c.exception))

    def test_wrong_arguments_are_type_errors(self):
        for kw in ({}, {"table": {}, "points": []}):
            with self.assertRaises(TypeError):
                hook_point.open(stack=self.stack, fail=die, **kw)
        with self.assertRaises(TypeError):
            hook_point.open([str(self.points)], lists=[], entries={}, stack=self.stack, fail=die)
        with self.assertRaises(TypeError):
            hook_point.open([str(self.points)], stack="", fail=die)
        with self.assertRaises(TypeError):
            hook_point.open([str(self.points)], stack=self.stack, fail=None)


if __name__ == "__main__":
    unittest.main()
