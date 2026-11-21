"""Test aos-hook fire through bin/aos-hook: the stdout line, event data from stdin only, name order with the same data for every handler, failing and timed-out handlers, lists layered and turned off, bad lists and arguments (real aos-exec; no daemon)."""
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


class HookCli(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aos-hook-cli-")
        self.addCleanup(tmp.cleanup)
        self.d = Path(os.path.realpath(tmp.name))
        self.stack = self.d / "stack"
        self.list = self.d / "hookeds.json"
        self.hooks = {}
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_", "T_"))}
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def write(self, name, doc):
        p = self.d / name
        p.write_text(json.dumps(doc) if not isinstance(doc, str) else doc)
        return p

    def handler(self, name, body, py=False, **entry):
        """A handler (sh, or python3 with py=True) put on the list as hook NAME."""
        p = self.d / ("h_" + name)
        p.write_text(("#!/usr/bin/env python3\nimport json, sys\nev = json.load(sys.stdin)\n" if py else "#!/bin/sh\n") + body + "\n")
        p.chmod(0o755)
        self.hooks[name] = dict({"event": "before_save", "handler": p.name}, **entry)
        self.write("hookeds.json", dict({"description": "test hooks"}, **self.hooks))

    def run_hook(self, *args, stdin="", env=None):
        return subprocess.run([sys.executable, str(HOOK)] + [str(a) for a in args], input=stdin, capture_output=True,
                              text=True, env=dict(self.env, **(env or {})), cwd=self.d, timeout=60)

    def fire(self, *args, **kw):
        return self.run_hook("fire", "--list", self.list, "--stack", self.stack, *args, **kw)

    def assertError(self, r, code, part=""):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.startswith("aos-hook: error: %s " % code), r.stderr)
        self.assertIn(part, r.stderr)

    def result(self, r, code=0):
        self.assertEqual(r.returncode, code, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 1, r.stdout)
        out = json.loads(lines[0])
        self.assertEqual(set(out), {"event", "hooks"})
        for h in out["hooks"]:
            self.assertEqual(set(h), {"hook", "code", "stdout", "error"})
        return out

    # ---- the shape of the command
    def test_help_and_subcommands(self):
        r = self.run_hook("--help")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("usage: aos-hook fire", r.stdout)
        self.assertIn("--stop-on-nonzero", self.run_hook("fire", "--help").stdout)
        self.assertError(self.run_hook(), "ArgumentsBad", "missing subcommand")
        for gone in ("points", "check", "shoot"):
            self.assertError(self.run_hook(gone), "CommandUnknown")
        self.assertError(self.run_hook("fire", "--nope"), "FlagUnknown")
        for gone in ("--field", "--field-file", "--field-default", "--points", "--agent"):
            self.assertError(self.run_hook("fire", gone, "x", "before_save"), "FlagUnknown")
        self.assertError(self.run_hook("fire", "--stack", self.stack, "before_save"), "ArgumentsBad", "--list")
        self.assertError(self.run_hook("fire", "--def", self.d, "--list", self.list, "--stack", self.stack, "before_save"),
                         "ArgumentsBad", "not both")
        self.assertError(self.fire(), "ArgumentsBad", "give one EVENT")
        self.assertError(self.fire("a", "b"), "ArgumentsBad", "give one EVENT")

    # ---- fire: exit 0, the line, -q
    def test_nobody_listens(self):
        out = self.result(self.fire("before_save", stdin=json.dumps({"file": "a.txt"})))
        self.assertEqual(out, {"event": "before_save", "hooks": []})
        r = self.fire("-q", "before_save")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.handler("other", "exit 3", event="after_save")              # another event's hook does not run
        self.assertEqual(self.result(self.fire("before_save"))["hooks"], [])

    def test_data_from_stdin(self):
        self.handler("seen", 'cat > "$AOS_STACK/seen.json"')
        stdin = json.dumps({"file": "in.txt", "size": 1, "extra": [1], "event": "spoofed", "hook": "x"})
        out = self.result(self.fire("before_save", stdin=stdin, env={"T_SIZE": "42"}))
        self.assertEqual(out["hooks"], [{"hook": "seen", "code": 0, "stdout": "", "error": None}])
        cell = self.stack / "hookeds" / "seen"
        seen = json.loads((cell / "seen.json").read_text())
        self.assertEqual(seen, {"event": "before_save", "hook": "seen", "stack": str(self.stack),
                                "file": "in.txt", "size": 1, "extra": [1]})   # event / hook / stack win; no env fields
        self.assertEqual(json.loads((cell / "event.json").read_text()), seen)
        for empty in ("", " \n"):
            self.result(self.fire("before_save", stdin=empty))
            self.assertEqual(set(json.loads((cell / "seen.json").read_text())), {"event", "hook", "stack"})
        self.assertError(self.fire("before_save", stdin="{"), "ArgumentsBad", "stdin is not JSON")
        self.assertError(self.fire("before_save", stdin="[1]"), "ArgumentsBad", "JSON object")

    def test_order_and_same_data(self):
        self.handler("b_second", 'import os\nprint(json.dumps(ev["file"]))\nopen(os.environ["AOS_STACK"] + "/../../order", "a").write("b")', py=True)
        self.handler("a_first", 'import os\nprint(json.dumps({"file": "changed"}))\nopen(os.environ["AOS_STACK"] + "/../../order", "a").write("a")\nsys.exit(10)', py=True)
        out = self.result(self.fire("before_save", stdin='{"file": "notes"}'))
        self.assertEqual([(h["hook"], h["code"], h["stdout"]) for h in out["hooks"]],
                         [("a_first", 10, '{"file": "changed"}\n'), ("b_second", 0, '"notes"\n')])   # not blocked, not changed
        self.assertEqual((self.stack / "order").read_text(), "ab")

    def test_failing_hooks(self):
        self.handler("a_boom", "echo out; exit 3")
        self.handler("b_after", "echo 'not json'")
        r = self.fire("before_save")
        out = self.result(r)
        self.assertEqual(out["hooks"], [{"hook": "a_boom", "code": 3, "stdout": "out\n", "error": None},
                                        {"hook": "b_after", "code": 0, "stdout": "not json\n", "error": None}])
        self.assertEqual(r.stderr, "")
        self.hooks = {}
        self.handler("slow", "sleep 5", timeout_ms=200)
        r = self.fire("before_save")
        out = self.result(r)
        self.assertEqual(out["hooks"][0]["code"], None)
        self.assertIn("did not finish in 200 ms", out["hooks"][0]["error"])
        self.assertIn("aos-hook: warning: hook slow (event before_save): did not finish in 200 ms", r.stderr)
        self.hooks = {}
        self.handler("gone", "true")
        self.hooks["gone"]["handler"] = "no_such_handler"
        self.write("hookeds.json", self.hooks)
        h = self.result(self.fire("before_save"))["hooks"][0]          # aos-exec starts, the target is not there
        self.assertNotIn(h["code"], (0, None))

    def test_lists(self):
        self.handler("a", "echo a")
        self.handler("b", "echo b")
        off = self.write("off.json", {"description": "turn a off", "a": None})
        more = self.write("more.json", {"b": {"event": "before_save", "handler": str(self.d / "h_a")}})
        out = self.result(self.fire("--list", off, "--list", self.d / "missing.json", "--list", more, "before_save"))
        self.assertEqual([(h["hook"], h["stdout"]) for h in out["hooks"]], [("b", "a\n")])   # later wins by name
        r = self.run_hook("fire", "--list", self.d / "missing.json", "--stack", self.stack, "before_save")
        self.assertEqual(self.result(r)["hooks"], [])
        self.handler("x", "true", intercept=False, on_error="continue", condition="ann")   # other keys are kept, not read
        self.assertEqual(len(self.result(self.fire("before_save"))["hooks"]), 3)

    def test_bad_inputs(self):
        self.assertError(self.run_hook("fire", "--list", self.list, "before_save"), "StackMissing")
        self.assertEqual(self.run_hook("fire", "--list", self.list, "-q", "before_save",
                                       env={"AOS_STACK": str(self.stack)}).returncode, 0)
        self.assertEqual(self.result(self.fire("anything_at_all"))["event"], "anything_at_all")   # event names are not checked
        for hooks, part in (({"h": {"handler": "x"}}, "event must be a non-empty string"),
                            ({"h": {"event": "before_save"}}, "handler must be"),
                            ({"h": {"event": "before_save", "handler": "x", "timeout_ms": -1}}, "timeout_ms"),
                            ({".h": {"event": "before_save", "handler": "x"}}, "hook name '.h'"),
                            ({"h": [1]}, "must be a JSON object or null")):
            self.write("hookeds.json", hooks)
            self.assertError(self.fire("before_save"), "HooksBad", part)
        self.write("hookeds.json", "[]")
        self.assertError(self.fire("before_save"), "HooksBad", "must be a JSON object")
        self.write("hookeds.json", "{")
        self.assertError(self.fire("before_save"), "HooksBad", "cannot read")


if __name__ == "__main__":
    unittest.main()
