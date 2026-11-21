"""Test aos-hook fire --def DEF_DIR through bin/aos-hook: the hookeds of interfaces.json as a string, an array and a directive, the stack's same-named copy on top, no hookeds = no hooks, and the mistakes (real aos-exec; no daemon)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
HOOK = PROTO / "bin" / "aos-hook"


class HookCliDef(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aos-hook-def-")
        self.addCleanup(tmp.cleanup)
        self.d = Path(os.path.realpath(tmp.name))
        self.defn, self.stack, self.shared = self.d / "def", self.d / "stack", self.d / "shared"
        for p in (self.defn, self.stack, self.shared):
            p.mkdir()
        self.interfaces("hookeds.json")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_", "T_"))}
        self.env.update(PYTHONDONTWRITEBYTECODE="1", AOS_HOME=str(PROTO), T_SHARED=str(self.shared))

    def interfaces(self, hookeds=None, **more):
        doc = dict({"aos-agent": {"entry": "body.json"}}, **more)
        if hookeds is not None:
            doc["hookeds"] = hookeds
        (self.defn / "interfaces.json").write_text(json.dumps(doc))

    def handler(self, name, body):
        """An executable in the definition folder that prints NAME and runs body."""
        p = self.defn / ("h_" + name)
        p.write_text("#!/bin/sh\necho %s\n%s\n" % (name, body))
        p.chmod(0o755)
        return str(p)

    def write(self, path, hooks):
        path.write_text(json.dumps(dict({"description": "test"}, **hooks)))

    def entry(self, name, body="", event="after_stop"):
        return {"event": event, "handler": self.handler(name, body)}

    def fire(self, *args, event="after_stop", stdin=""):
        return subprocess.run([sys.executable, str(HOOK), "fire", "--def", str(self.defn)] + [str(a) for a in args]
                              + [event], input=stdin, capture_output=True, text=True, env=self.env, cwd=self.d, timeout=60)

    def ran(self, r, code=0):
        self.assertEqual(r.returncode, code, r.stderr)
        return [h["hook"] for h in json.loads(r.stdout)["hooks"]]

    def assertError(self, r, code, part=""):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-hook: error: %s " % code), r.stderr)
        self.assertIn(part, r.stderr)

    def test_string_with_the_stack_copy_on_top(self):
        self.write(self.defn / "hookeds.json", {"a_seen": dict(self.entry("a_seen"), handler="h_a_seen"),
                                                "b_off": self.entry("b_off", "exit 3")})
        r = self.fire("--stack", self.stack, stdin='{"code": 3}')
        self.assertEqual(self.ran(r), ["a_seen", "b_off"])
        self.write(self.stack / "hookeds.json", {"b_off": None, "c_mine": self.entry("c_mine")})   # off and one more
        r = self.fire("--stack", self.stack)
        self.assertEqual(self.ran(r), ["a_seen", "c_mine"])
        self.assertEqual(json.loads((self.stack / "hookeds" / "a_seen" / "event.json").read_text())["event"], "after_stop")
        r = self.fire("--stack", self.d / "other")                             # another stack: only the definition's
        self.assertEqual(self.ran(r), ["a_seen", "b_off"])

    def test_array_and_directive(self):
        self.interfaces(["base.json", {"$env": "T_SHARED", "$path": "/shared.json"}, "hookeds.json"])
        self.write(self.defn / "base.json", {"a": self.entry("a"), "b": self.entry("b")})
        self.write(self.shared / "shared.json", {"b": None, "s": self.entry("s")})   # a directive item: no stack copy
        self.write(self.defn / "hookeds.json", {"d": self.entry("d")})
        self.assertEqual(self.ran(self.fire("--stack", self.stack)), ["a", "d", "s"])
        self.write(self.stack / "base.json", {"b": self.entry("b")})            # the stack copy of base.json
        self.write(self.stack / "shared.json", {"x": self.entry("x")})          # not read: shared.json is a directive item
        self.write(self.stack / "hookeds.json", {"a": None})
        self.assertEqual(self.ran(self.fire("--stack", self.stack)), ["b", "d", "s"])

    def test_no_hookeds_no_hooks(self):
        self.interfaces()
        self.write(self.defn / "hookeds.json", {"a": self.entry("a", "exit 3")})   # there, but not named
        self.write(self.stack / "hookeds.json", {"b": self.entry("b", "exit 3")})
        r = self.fire("--stack", self.stack, "--stop-on-nonzero")
        self.assertEqual(self.ran(r), [])
        (self.defn / "interfaces.json").unlink()
        self.assertEqual(self.ran(self.fire("--stack", self.stack)), [])
        self.interfaces("missing.json")                                        # named but not there: no hooks
        self.assertEqual(self.ran(self.fire("--stack", self.stack)), [])

    def test_stop_on_nonzero_with_def(self):
        self.write(self.defn / "hookeds.json", {"a": self.entry("a", "exit 10", "before_run"),
                                                "b": self.entry("b", "", "before_run")})
        r = self.fire("-q", "--stop-on-nonzero", "--stack", self.stack, event="before_run")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (10, "", ""))

    def test_mistakes(self):
        self.assertError(self.fire("--list", self.d / "x.json", "--stack", self.stack), "ArgumentsBad", "not both")
        r = subprocess.run([sys.executable, str(HOOK), "fire", "--def", str(self.d / "nope"), "--stack", str(self.stack),
                            "after_stop"], capture_output=True, text=True, env=self.env, timeout=60, stdin=subprocess.DEVNULL)
        self.assertError(r, "ArgumentsBad", "definition folder")
        self.assertError(self.fire(), "StackMissing")
        self.interfaces(7)
        self.assertError(self.fire("--stack", self.stack), "InterfaceBad", "hookeds")
        self.interfaces({"$env": "T_NOT_SET_AT_ALL", "$path": "/x.json"})
        r = self.fire("--stack", self.stack)                                   # aos-directive's own line comes first
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("aos-hook: error: InterfaceBad ", r.stderr)
        self.assertIn("cannot be resolved", r.stderr)
        (self.defn / "interfaces.json").write_text("{")
        self.assertError(self.fire("--stack", self.stack), "InterfaceBad", "cannot read")
        self.interfaces("hookeds.json")
        (self.defn / "hookeds.json").write_text(json.dumps({"h": {"event": "after_stop"}}))
        self.assertError(self.fire("--stack", self.stack), "HooksBad", "handler must be")


if __name__ == "__main__":
    unittest.main()
