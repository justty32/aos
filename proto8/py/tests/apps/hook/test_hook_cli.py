"""Test aos-hook (fire, points, check) through bin/aos-hook: exit codes 0/10/1, the stdout line, where event data comes from, changes and their types, blocking, failing hooks, bad declarations and lists (real aos-exec; no daemon)."""
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
LOOP = PROTO / "py" / "aos" / "apps" / "hook" / "loop_points.json"
POINTS = {"description": "a test provider", "provider": "saver", "points": {
    "before_save": {"when": "before a file is saved", "phase": "before",
                    "fields": {"file": "the file name", "size": {"about": "bytes", "env": "T_SIZE", "type": "int"},
                               "who": {"about": "user", "env": "T_WHO"}},
                    "condition": "who", "change": {"file": "nonempty_string"}, "block": True,
                    "if_blocked": "not saved"},
    "after_save": {"when": "after a file is saved", "phase": "after", "fields": {"file": "the file name", "meta": "extra"},
                   "change": {"meta": "object"}, "entry_keys": ["every_ms"]}}}


class HookCli(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aos-hook-cli-")
        self.addCleanup(tmp.cleanup)
        self.d = Path(os.path.realpath(tmp.name))
        self.stack = self.d / "stack"
        self.points = self.write("hook_points.json", POINTS)
        self.list = self.d / "hooks.json"
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
        self.write("hooks.json", {"hooks": self.hooks})

    def run_hook(self, *args, stdin="", env=None):
        return subprocess.run([sys.executable, str(HOOK)] + [str(a) for a in args], input=stdin, capture_output=True,
                              text=True, env=dict(self.env, **(env or {})), cwd=self.d, timeout=60)

    def fire(self, *args, **kw):
        return self.run_hook("fire", "--points", self.points, "--list", self.list, "--stack", self.stack, *args, **kw)

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
        self.assertEqual(set(out), {"data", "changed", "blocked", "hook", "text"})
        return out

    # ---- the shape of the command
    def test_help_and_subcommands(self):
        r = self.run_hook("--help")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("usage: aos-hook SUBCOMMAND", r.stdout)
        self.assertIn("usage: aos-hook fire", self.run_hook("fire", "--help").stdout)
        self.assertError(self.run_hook(), "ArgumentsBad", "missing subcommand")
        self.assertError(self.run_hook("shoot"), "CommandUnknown")
        self.assertError(self.run_hook("fire", "--nope"), "FlagUnknown")
        self.assertError(self.run_hook("fire", "before_save"), "ArgumentsBad", "--points")
        self.assertError(self.run_hook("fire", "--agent", self.d, "before_save"), "ArgumentsBad", "not available yet")

    # ---- fire: exit 0, data, -q
    def test_nobody_listens(self):
        out = self.result(self.fire("--field", "file=a.txt", "before_save"))
        self.assertEqual(out, {"data": {"file": "a.txt", "size": None, "who": None}, "changed": [], "blocked": False,
                               "hook": None, "text": ""})
        r = self.fire("-q", "before_save")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_data_sources(self):
        stdin = json.dumps({"file": "in.txt", "size": 1, "who": "stdin", "extra": [1]})
        out = self.result(self.fire("before_save", stdin=stdin, env={"T_SIZE": " ", "T_WHO": ""}))
        self.assertEqual(out["data"], {"file": "in.txt", "size": 1, "who": "stdin", "extra": [1]})   # empty env keeps stdin
        out = self.result(self.fire("before_save", stdin=stdin, env={"T_SIZE": "42", "T_WHO": " ann "}))
        self.assertEqual((out["data"]["size"], out["data"]["who"]), (42, "ann"))
        out = self.result(self.fire("--field", "size=7", "--field", "who=bob", "--field", "who=cy", "before_save",
                                    stdin=stdin, env={"T_SIZE": "42"}))
        self.assertEqual((out["data"]["size"], out["data"]["who"]), (7, "cy"))
        self.write("name.txt", "  from_file.txt\n")
        out = self.result(self.fire("--field-file", "file=name.txt", "--field-file", "who=missing.txt",
                                    "--field-default", "who=dflt", "--field-default", "file=unused", "before_save"))
        self.assertEqual((out["data"]["file"], out["data"]["who"]), ("from_file.txt", "dflt"))
        for args, part in ((["--field", "size=many"], "is a whole number"), (["--field", "file"], "NAME=VALUE"),
                           (["--field", "file=a", "--field-file", "file=b"], "give it once")):
            self.assertError(self.fire(*args, "before_save"), "ArgumentsBad", part)
        self.assertError(self.fire("before_save", env={"T_SIZE": "1.5"}), "ArgumentsBad", "$T_SIZE")
        self.assertError(self.fire("before_save", stdin="{"), "ArgumentsBad", "stdin is not JSON")
        self.assertError(self.fire("before_save", stdin="[1]"), "ArgumentsBad", "JSON object")

    def test_change_block_and_order(self):
        self.handler("a_deny", 'if ev["file"].startswith("secret"):\n    print("no secrets")\n    sys.exit(10)', py=True)
        self.handler("b_rename", "f=$(python3 -c 'import json,sys; print(json.load(sys.stdin)[\"file\"])')\n"
                                 "printf '{\"file\": \"%s.bak\", \"size\": 9}' \"$f\"")
        out = self.result(self.fire("--field", "file=notes", "before_save"))
        self.assertEqual((out["data"]["file"], out["data"]["size"], out["changed"]), ("notes.bak", None, ["file"]))
        self.assertTrue((self.stack / "hooks" / "b_rename" / "event.json").is_file())
        out = self.result(self.fire("--field", "file=secret", "before_save"), 10)
        self.assertEqual((out["blocked"], out["hook"], out["text"]), (True, "a_deny", "no secrets\n"))
        self.assertEqual(out["data"]["file"], "secret")
        self.assertEqual(self.fire("-q", "--field", "file=secret", "before_save").returncode, 10)

    def test_condition_and_lists(self):
        self.handler("only_ann", "echo '{\"file\": \"ann\"}'", condition="ann")
        self.assertEqual(self.result(self.fire("--field", "who=bob", "--field", "file=x", "before_save"))["changed"], [])
        self.assertEqual(self.result(self.fire("--field", "who=ann", "--field", "file=x", "before_save"))["data"]["file"], "ann")
        off = self.write("off.json", {"hooks": {"only_ann": None}})
        out = self.result(self.fire("--list", off, "--list", self.d / "missing.json", "--field", "who=ann", "before_save"))
        self.assertEqual(out["changed"], [])

    def test_failing_hooks(self):
        self.handler("boom", "exit 3")
        self.assertError(self.fire("before_save"), "HookFailed", "hook boom (event before_save) failed: exited 3")
        self.handler("boom", "exit 3", on_error="continue")
        r = self.fire("before_save")
        self.assertEqual(r.returncode, 0)
        self.assertIn("aos-hook: warning: hook boom (event before_save) failed: exited 3", r.stderr)
        self.handler("boom", "echo 'not json'")
        self.assertError(self.fire("before_save"), "HookFailed", "stdout is not JSON")
        self.handler("boom", "sleep 5", timeout_ms=200)
        self.assertError(self.fire("before_save"), "HookFailed", "did not finish in 200 ms")

    def test_change_types(self):
        self.handler("a_empty", "echo '{\"file\": \" \"}'", on_error="continue")
        self.handler("b_seen", 'cat > "$AOS_STACK/seen.json"')
        r = self.fire("--field", "file=keep", "before_save")
        self.assertIn("file in stdout must be a non-empty string", r.stderr)
        self.assertEqual(self.result(r)["data"]["file"], "keep")
        self.assertEqual(json.loads((self.stack / "hooks" / "b_seen" / "seen.json").read_text())["file"], "keep")
        self.hooks = {}
        self.handler("meta", "echo '{\"meta\": [1]}'", event="after_save")
        self.assertError(self.fire("after_save"), "HookFailed", "meta in stdout must be a JSON object")
        self.handler("meta", "echo '{\"meta\": {\"k\": 1}}'", event="after_save")
        self.assertEqual(self.result(self.fire("after_save"))["data"]["meta"], {"k": 1})

    def test_bad_inputs(self):
        self.assertError(self.fire("before_sav"), "EventUnknown", "points: before_save, after_save")
        r = self.run_hook("fire", "--points", self.points, "before_save")
        self.assertError(r, "StackMissing")
        self.assertEqual(self.run_hook("fire", "--points", self.points, "-q", "before_save",
                                       env={"AOS_STACK": str(self.stack)}).returncode, 0)
        bad = self.write("bad.json", {"provider": "x", "points": {"Bad-Name": {}}})
        self.assertError(self.run_hook("points", "--points", bad), "PointsBad", "may only have a-z")
        other = json.loads(json.dumps(POINTS))
        other["points"]["before_save"]["block"] = False
        other["points"]["before_save"].pop("if_blocked")
        two = self.write("two.json", other)
        self.assertError(self.run_hook("check", "--points", self.points, "--points", two), "PointsBad", "block differs")
        for hooks, part in (({"h": {"event": "nope", "handler": "x"}}, "event must be one of"),
                            ({"h": {"event": "before_save", "handler": "x", "every_ms": 5}}, "every_ms is only for event after_save"),
                            ({".h": {"event": "before_save", "handler": "x"}}, "hook name '.h'")):
            self.write("hooks.json", {"hooks": hooks})
            self.assertError(self.fire("before_save"), "HooksBad", part)
            self.assertError(self.run_hook("check", "--points", self.points, "--list", self.list), "HooksBad", part)
        self.write("hooks.json", "[]")
        self.assertError(self.fire("before_save"), "HooksBad", "must be a JSON object")

    # ---- the loop points, points and check
    def test_loop_points(self):
        self.hooks = {}
        self.handler("skip", "exit 10", event="before_run", condition="act")
        args = ("fire", "--points", LOOP, "--list", self.list, "--stack", self.stack)
        out = self.result(self.run_hook(*args, "--field-file", "stage=nope", "--field-default", "stage=act", "before_run",
                                        env={"AOS_LOOP_RUNS": "3"}), 10)
        self.assertEqual((out["data"], out["hook"]), ({"counter_runs": 3, "stage": "act"}, "skip"))
        out = self.result(self.run_hook(*args, "after_stop", env={"AOS_LOOP_CODE": "0", "AOS_LOOP_CAUSE": " stop "}))
        self.assertEqual(out["data"], {"code": 0, "signal": None, "cause": "stop"})

    def test_points_and_check(self):
        r = self.run_hook("points", "--points", self.points)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "before_save  before  condition who  change file (nonempty_string)  can block")
        self.assertIn("  saver, if blocked: not saved", r.stdout)
        self.assertIn("  field size: bytes ($T_SIZE, int)", r.stdout)
        doc = json.loads(self.run_hook("points", "-j", "--points", self.points).stdout)
        self.assertEqual(list(doc), ["before_save", "after_save"])
        self.assertEqual(doc["before_save"]["said"][0]["provider"], "saver")
        self.handler("x", "true")
        r = self.run_hook("check", "--points", self.points, "--list", self.list)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout, "ok: 2 points from 1 declarations, 1 hooks from 1 lists\n")
        self.handler("later", "true", event="after_run")
        r = self.run_hook("check", "--points", self.points, "--points", LOOP, "--list", self.list)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("aos-hook: warning: hook later (in %s) is on point after_run, which nothing fires yet" % self.list, r.stderr)


if __name__ == "__main__":
    unittest.main()
