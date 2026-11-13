"""Verify the shared hook engine: entry validation, running handlers through aos-exec, replies, blocking, on_error, timeouts, ordering and conditions."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hook_run

EVENTS = {
    "before": {"condition": None, "intercept": ("body",), "block": True},
    "after": {"condition": "kind", "intercept": ("body", "note"), "block": False},
    "plain": {"condition": "kind", "intercept": (), "block": False},
}


class ValidateTests(unittest.TestCase):
    def test_validate_entry(self):
        good = {"event": "after", "handler": "h", "intercept": False, "async": True, "condition": ["a", "b"],
                "on_error": "continue", "timeout_ms": 5, "every_ms": "not ours"}
        self.assertIsNone(hook_run.validate_entry(good, EVENTS))
        self.assertIsNone(hook_run.validate_entry({"event": "before", "handler": {"$path": "h"}}, EVENTS))
        bad = (
            ([], "must be a JSON object or null"),
            ({"event": "nope", "handler": "h"}, "event must be one of before, after, plain"),
            ({"event": "after", "handler": ""}, "handler must be a non-empty string or a directive object"),
            ({"event": "after", "handler": {}}, "handler must be a non-empty string or a directive object"),
            ({"event": "after", "handler": "h", "intercept": 1}, "intercept must be true or false"),
            ({"event": "after", "handler": "h", "async": "no"}, "async must be true or false"),
            ({"event": "after", "handler": "h", "condition": ["a", 1]}, "condition must be a string or an array of strings"),
            ({"event": "before", "handler": "h", "condition": "a"}, "event before takes no condition"),
            ({"event": "after", "handler": "h", "on_error": "skip"}, "on_error must be stop or continue"),
            ({"event": "after", "handler": "h", "timeout_ms": 0}, "timeout_ms must be a positive integer"),
            ({"event": "after", "handler": "h", "timeout_ms": True}, "timeout_ms must be a positive integer"),
        )
        for entry, message in bad:
            with self.subTest(message=message, entry=entry):
                with self.assertRaises(hook_run.HooksBad) as caught:
                    hook_run.validate_entry(entry, EVENTS)
                self.assertEqual(str(caught.exception), message)


class FireTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = os.path.realpath(folder.name)
        self.stack = os.path.join(self.root, "stack")
        os.mkdir(self.stack)
        self.log = os.path.join(self.root, "log")
        self.entries = {}
        self.warned = []

    def hook(self, name, event, reply="", code=0, extra="", **keys):
        """一個 sh handler：把名字記進 log、印 reply、退 code；登記成一格。"""
        path = os.path.join(self.root, "handler_" + name)
        with open(path + ".reply", "w", encoding="utf-8") as f:
            f.write(reply if isinstance(reply, str) else json.dumps(reply))
        with open(path, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\ncat > '%s.stdin'\necho %s >> '%s'\n%s\ncat '%s.reply'\nexit %d\n"
                    % (path, name, self.log, extra, path, code))
        os.chmod(path, 0o755)
        entry = dict({"event": event, "handler": "handler_" + name}, **keys)
        hook_run.validate_entry(entry, EVENTS)
        self.entries[name] = hook_run.complete(entry, os.path.join(self.root, "hooks.json"))

    def fire(self, event, data, **more):
        return hook_run.fire(event, data, self.entries, self.stack, EVENTS, warn=self.warned.append, **more)

    def ran(self):
        try:
            with open(self.log, encoding="utf-8") as f:
                return f.read().split()
        except FileNotFoundError:
            return []

    def test_reply_changes_only_listed_keys(self):
        self.hook("a_quiet", "after")
        data = {"body": "old", "kind": "x"}
        result = self.fire("after", data)
        self.assertEqual(result, {"data": data, "changed": [], "blocked": False, "hook": None, "text": ""})
        self.assertIsNot(result["data"], data)

        self.hook("b_edit", "after", reply={"body": "new", "kind": "hacked", "other": 1})
        result = self.fire("after", data)
        self.assertEqual(result["data"], {"body": "new", "kind": "x"})
        self.assertEqual(result["changed"], ["body"])
        self.assertEqual(data, {"body": "old", "kind": "x"})

    def test_check_rejecting_a_value_is_a_hook_failure(self):
        self.hook("edit", "after", reply={"body": 5})
        seen = []

        def check(event, key, value):
            seen.append((event, key, value))
            if not isinstance(value, str):
                raise ValueError("body in stdout must be a string")

        with self.assertRaises(hook_run.HookFailed) as caught:
            self.fire("after", {"body": "old"}, check=check)
        self.assertEqual(str(caught.exception), "hook edit (event after) failed: body in stdout must be a string")
        self.assertEqual(seen, [("after", "body", 5)])

    def test_exit_10_blocks_only_on_block_events(self):
        self.hook("a_block", "before", reply="not json", code=10)
        self.hook("b_later", "before", reply={"body": "new"})
        result = self.fire("before", {"body": "old"})
        self.assertEqual(result, {"data": {"body": "old"}, "changed": [], "blocked": True, "hook": "a_block",
                                  "text": "not json"})
        self.assertEqual(self.ran(), ["a_block"])

        self.hook("c_after", "after", reply={"body": "new"}, code=10)
        result = self.fire("after", {"body": "old"})
        self.assertFalse(result["blocked"])
        self.assertIsNone(result["hook"])
        self.assertEqual(result["data"], {"body": "new"})

    def test_other_exit_codes_follow_on_error(self):
        self.hook("a_fail", "after", reply={"body": "new"}, code=3, on_error="continue")
        self.hook("b_edit", "after", reply={"note": "kept"})
        result = self.fire("after", {"body": "old"})
        self.assertEqual(self.warned, ["hook a_fail (event after) failed: exited 3; going on without it (on_error: continue)"])
        self.assertEqual(result["data"], {"body": "old", "note": "kept"})
        self.assertEqual(result["changed"], ["note"])

        self.entries["a_fail"]["on_error"] = "stop"
        os.remove(self.log)
        with self.assertRaises(hook_run.HookFailed) as caught:
            self.fire("after", {"body": "old"})
        self.assertEqual(str(caught.exception), "hook a_fail (event after) failed: exited 3")
        self.assertEqual(self.ran(), ["a_fail"])

    def test_timeout_kills_the_group_and_follows_on_error(self):
        child = os.path.join(self.root, "child.pid")
        self.hook("slow", "after", extra="sleep 30 &\necho $! > '%s'\nsleep 30" % child, timeout_ms=300, on_error="continue")
        started = time.monotonic()
        result = self.fire("after", {"body": "old"})
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(self.warned, ["hook slow (event after) failed: did not finish in 300 ms (its process group was killed)"
                                       "; going on without it (on_error: continue)"])
        self.assertEqual(result["changed"], [])
        with open(child, encoding="utf-8") as f:
            pid = int(f.read())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

        self.entries["slow"]["on_error"] = "stop"
        with self.assertRaises(hook_run.HookFailed) as caught:
            self.fire("after", {"body": "old"})
        self.assertEqual(str(caught.exception),
                         "hook slow (event after) failed: did not finish in 300 ms (its process group was killed)")

    def test_async_and_intercept_false_ignore_the_reply(self):
        done = os.path.join(self.root, "done")
        self.hook("bg", "before", reply={"body": "new"}, code=10, extra="sleep 1\ntouch '%s'" % done, **{"async": True})
        started = time.monotonic()
        result = self.fire("before", {"body": "old"})
        self.assertLess(time.monotonic() - started, 0.9)
        self.assertFalse(os.path.exists(done))
        self.assertEqual(result, {"data": {"body": "old"}, "changed": [], "blocked": False, "hook": None, "text": ""})
        deadline = time.monotonic() + 10
        while not os.path.exists(done) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(os.path.exists(done))
        time.sleep(0.2)                          # 讓它印完退掉，暫存夾才清得掉

        del self.entries["bg"]
        self.hook("deaf", "before", reply={"body": "new"}, code=10, intercept=False)
        self.hook("z_next", "before")
        result = self.fire("before", {"body": "old"})
        self.assertEqual(result, {"data": {"body": "old"}, "changed": [], "blocked": False, "hook": None, "text": ""})
        self.assertEqual(self.ran(), ["bg", "deaf", "z_next"])

    def test_hooks_run_in_name_order_and_see_earlier_changes(self):
        self.hook("b_second", "after", reply={"note": "two"})
        self.hook("a_first", "after", reply={"body": "one"})
        self.hook("c_third", "after")
        result = self.fire("after", {"body": "old"})
        self.assertEqual(self.ran(), ["a_first", "b_second", "c_third"])
        self.assertEqual(result["data"], {"body": "one", "note": "two"})
        self.assertEqual(result["changed"], ["body", "note"])
        seen = {}
        for name in ("a_first", "b_second", "c_third"):
            with open(os.path.join(self.root, "handler_%s.stdin" % name), encoding="utf-8") as f:
                seen[name] = json.load(f)
        self.assertEqual(seen["a_first"]["body"], "old")
        self.assertNotIn("note", seen["a_first"])
        self.assertEqual(seen["b_second"]["body"], "one")
        self.assertEqual((seen["c_third"]["body"], seen["c_third"]["note"]), ("one", "two"))

    def test_condition_and_only(self):
        self.hook("any", "plain")
        self.hook("one", "plain", condition="x")
        self.hook("some", "plain", condition=["y", "z"])
        self.hook("elsewhere", "after")
        self.fire("plain", {"kind": "x"})
        self.assertEqual(self.ran(), ["any", "one"])
        os.remove(self.log)
        self.fire("plain", {"kind": "z"})
        self.assertEqual(self.ran(), ["any", "some"])
        os.remove(self.log)
        self.fire("plain", {})
        self.assertEqual(self.ran(), ["any"])
        os.remove(self.log)
        self.fire("plain", {"kind": "x"}, only=["one", "some"])
        self.assertEqual(self.ran(), ["one"])
        with self.assertRaises(ValueError) as caught:
            self.fire("nope", {})
        self.assertEqual(str(caught.exception), "unknown hook event nope")

    def test_event_json(self):
        self.hook("look", "after")
        self.fire("after", {"body": "ö", "kind": "x", "event": "fake", "hook": "fake", "stack": "fake"})
        expected = {"event": "after", "hook": "look", "stack": self.stack, "body": "ö", "kind": "x"}
        cell = os.path.join(self.stack, "hooks", "look")
        with open(os.path.join(cell, "event.json"), encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(json.loads(text), expected)
        self.assertTrue(text.endswith("\n") and "ö" in text, text)
        self.assertEqual(os.listdir(cell), ["event.json"])
        with open(os.path.join(self.root, "handler_look.stdin"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), expected)


if __name__ == "__main__":
    unittest.main()
