"""Verify the minimal hook engine: reading hookeds lists (aos.hook_lists), running handlers through aos-exec in name order with the same data, timeouts, and handler directives."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aos import hook_lists, hook_run


class ListTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = os.path.realpath(folder.name)

    def write(self, name, doc):
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))
        return path

    def test_check_entry_and_name(self):
        hook_lists.check_entry({"event": "x", "handler": "h", "timeout_ms": 0, "condition": 5, "on_error": "nope"})
        hook_lists.check_entry({"event": "x", "handler": {"$path": "h"}})
        bad = (([], "must be a JSON object or null"),
               ({"handler": "h"}, "event must be a non-empty string"),
               ({"event": "", "handler": "h"}, "event must be a non-empty string"),
               ({"event": "x", "handler": ""}, "handler must be a non-empty string or a directive object"),
               ({"event": "x", "handler": {}}, "handler must be a non-empty string or a directive object"),
               ({"event": "x", "handler": "h", "timeout_ms": -1}, "timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit)"),
               ({"event": "x", "handler": "h", "timeout_ms": True}, "timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit)"))
        for entry, message in bad:
            with self.subTest(entry=entry):
                with self.assertRaises(hook_lists.HooksBad) as cm:
                    hook_lists.check_entry(entry)
                self.assertEqual(str(cm.exception), message)
        for name in ("", "a/b", ".x", "description"):
            with self.subTest(name=name), self.assertRaises(hook_lists.HooksBad):
                hook_lists.check_name(name)

    def test_load_layers(self):
        a = self.write("a.json", {"description": "first", "x": {"event": "e", "handler": "hx"},
                                  "y": {"event": "e", "handler": "hy"}})
        b = self.write("b.json", {"x": {"event": "f", "handler": "../hx2"}, "y": None})
        got = hook_lists.load([a, b, os.path.join(self.root, "missing.json")])
        self.assertEqual(sorted(got), ["x"])
        self.assertEqual(got["x"], {"event": "f", "handler": "../hx2", "from": b, "base": self.root})
        self.assertEqual(hook_lists.read(os.path.join(self.root, "missing.json")), {})

    def test_load_bad(self):
        cases = ((self.write("n.json", "[1]"), "must be a JSON object"),
                 (self.write("j.json", "{"), "cannot read"),
                 (self.write("e.json", {"x": {"event": "e"}}), "hook x in "),
                 (self.write("m.json", {"a/b": None}), "hook name 'a/b'"))
        for path, word in cases:
            with self.subTest(path=path):
                with self.assertRaises(hook_lists.HooksBad) as cm:
                    hook_lists.load([path])
                self.assertIn(word, str(cm.exception))

    def test_caller_check(self):
        path = self.write("c.json", {"x": {"event": "e", "handler": "h", "every_ms": 0}})

        def check(entry):
            if "every_ms" in entry:
                raise hook_lists.HooksBad("no every_ms here")
        with self.assertRaises(hook_lists.HooksBad) as cm:
            hook_lists.load([path], check)
        self.assertEqual(str(cm.exception), "hook x in %s: no every_ms here" % path)


class FireTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = os.path.realpath(folder.name)
        self.stack = os.path.join(self.root, "stack")
        os.mkdir(self.stack)
        self.log = os.path.join(self.root, "log")
        self.entries = {}

    def hook(self, name, event, reply="", code=0, extra="", **keys):
        """A sh handler: logs its name, prints reply, exits code; listed as one entry."""
        path = os.path.join(self.root, "handler_" + name)
        with open(path + ".reply", "w", encoding="utf-8") as f:
            f.write(reply)
        with open(path, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\ncat > '%s.stdin'\necho %s >> '%s'\n%s\ncat '%s.reply'\nexit %d\n"
                    % (path, name, self.log, extra, path, code))
        os.chmod(path, 0o755)
        entry = dict({"event": event, "handler": "handler_" + name}, **keys)
        hook_lists.check_entry(entry)
        self.entries[name] = dict(entry, **{"from": os.path.join(self.root, "hookeds.json"), "base": self.root})

    def ran(self):
        try:
            with open(self.log, encoding="utf-8") as f:
                return f.read().split()
        except FileNotFoundError:
            return []

    def test_name_order_same_data_codes_and_stdout(self):
        self.hook("b", "e", reply='{"k": "changed"}')
        self.hook("a", "e", reply="hi\n", code=10)
        self.hook("c", "e", code=3)
        self.hook("z", "other")
        got = hook_run.fire("e", {"k": "v"}, self.entries, self.stack)
        self.assertEqual(self.ran(), ["a", "b", "c"])
        self.assertEqual([(r["hook"], r["code"], r["stdout"], r["error"]) for r in got],
                         [("a", 10, "hi\n", None), ("b", 0, '{"k": "changed"}', None), ("c", 3, "", None)])
        for name in ("a", "b", "c"):
            with open(os.path.join(self.root, "handler_%s.stdin" % name), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["k"], "v")       # nobody's stdout changes what the next one gets

    def test_stop_on_nonzero(self):
        self.hook("a", "e")
        self.hook("b", "e", code=10)
        self.hook("c", "e")
        got = hook_run.fire("e", {}, self.entries, self.stack, stop_on_nonzero=True)
        self.assertEqual([r["hook"] for r in got], ["a", "b"])
        self.assertEqual(self.ran(), ["a", "b"])

    def test_nobody_listens(self):
        self.assertEqual(hook_run.fire("e", {}, {}, self.stack), [])
        self.assertFalse(os.path.exists(os.path.join(self.stack, hook_run.CELLS)))

    def test_event_json(self):
        self.hook("look", "after")
        hook_run.fire("after", {"body": "ö", "event": "fake", "hook": "fake", "stack": "fake"}, self.entries, self.stack)
        expected = {"event": "after", "hook": "look", "stack": self.stack, "body": "ö"}
        cell = os.path.join(self.stack, "hookeds", "look")
        with open(os.path.join(cell, "event.json"), encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(json.loads(text), expected)
        self.assertTrue(text.endswith("\n") and "ö" in text, text)
        self.assertEqual(os.listdir(cell), ["event.json"])

    def test_zero_timeout_waits(self):
        self.hook("slow", "e", extra="sleep 0.3", timeout_ms=0)
        self.assertEqual(hook_run.fire("e", {}, self.entries, self.stack)[0]["code"], 0)

    def test_timeout_kills_the_group(self):
        marker = os.path.join(self.root, "child_alive")
        self.hook("slow", "e", extra="(sleep 3; touch '%s') & sleep 5" % marker, timeout_ms=300)
        start = time.monotonic()
        got = hook_run.fire("e", {}, self.entries, self.stack)
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(got[0]["code"], None)
        self.assertEqual(got[0]["error"], "did not finish in 300 ms (its process group was killed)")
        time.sleep(3.3)
        self.assertFalse(os.path.exists(marker))

    def test_cannot_start(self):
        self.entries["gone"] = {"event": "e", "handler": "nowhere", "from": os.path.join(self.root, "h.json"), "base": self.root}
        with mock.patch.dict(os.environ, {"PATH": os.path.join(self.root, "empty")}):
            got = hook_run.fire("e", {}, self.entries, self.stack)
        self.assertIsNone(got[0]["code"])
        self.assertTrue(got[0]["error"].startswith("cannot start: "), got[0]["error"])


@unittest.skipUnless(__import__("shutil").which("aos-directive"), "aos-directive not on PATH")
class TargetAt(unittest.TestCase):
    """A handler directive resolves from its place NAME/handler in its list: #./ and #../ count from there."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.realpath(self.tmp.name)
        self.path = os.path.join(self.root, "hookeds.json")
        self.doc = {"handler_dir": "top/h", "count": 5,
                    "a": {"event": "before", "path": "near/h", "handler": {"$ref": "#./path"}},
                    "b": {"event": "before", "handler": {"$ref": "#../handler_dir"}},
                    "c": {"event": "before", "handler": {"$ref": "#./nowhere"}},
                    "d": {"event": "before", "handler": {"$ref": "#/count"}}}
        with open(self.path, "w") as f:
            json.dump(self.doc, f)

    def entry(self, name):
        return dict(self.doc[name], **{"from": self.path, "base": self.root})

    def test_dot_and_dotdot(self):
        self.assertEqual(hook_run.target(self.entry("a"), "a"), os.path.join(self.root, "near/h"))
        self.assertEqual(hook_run.target(self.entry("b"), "b"), os.path.join(self.root, "top/h"))

    def test_reasons(self):
        with self.assertRaises(OSError) as cm:
            hook_run.target(self.entry("c"), "c")
        self.assertRegex(str(cm.exception), r"^cannot resolve handler directive: aos-directive exited \d+$")
        with self.assertRaises(OSError) as cm:
            hook_run.target(self.entry("d"), "d")
        self.assertEqual(str(cm.exception), "handler directive did not resolve to a non-empty path")

    def test_directive_error_line_is_swallowed(self):
        with tempfile.TemporaryFile() as tmp:
            saved = os.dup(2)
            os.dup2(tmp.fileno(), 2)
            try:
                with self.assertRaises(OSError):
                    hook_run.target(self.entry("c"), "c")
            finally:
                os.dup2(saved, 2)
                os.close(saved)
            tmp.seek(0)
            self.assertEqual(tmp.read(), b"")


if __name__ == "__main__":
    unittest.main()
