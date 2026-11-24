"""Test aos-tools add --uses N (11-24, the user's "self_tools --once ... or --twice"): a successful call counts down "uses" in the registry
that holds it, at 0 the entry is deleted (a tool it replaced comes back), failed calls do not count, ls and ls --json show what is left."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import env_helper  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / "bin" / "aos-tools"
FAIL = '''#!/usr/bin/env python3
import sys
if len(sys.argv) > 1 and sys.argv[1] == "--tooldef":
    print('{"description": "Always fails. Second sentence.", "parameters": {"type": "object", "properties": {}}}')
    sys.exit(0)
sys.stdin.read()
print("boom", file=sys.stderr)
sys.exit(3)
'''


OK = FAIL.replace("Always fails.", "Answers ok.").replace('print("boom", file=sys.stderr)\nsys.exit(3)', 'print("ok")')


class Uses(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-uses-"))
        (self.tmp / "lib").mkdir()
        for name, text in (("clock", OK), ("base_clock", OK), ("fails", FAIL)):
            f = self.tmp / "lib" / name
            f.write_text(text)
            f.chmod(f.stat().st_mode | stat.S_IXUSR)
        self.base = self.tmp / "defs" / "tools.json"
        self.base.parent.mkdir()
        self.base.write_text(json.dumps({"tools": {"clock": {"path": "../lib/base_clock"}}}))
        self.mine = self.tmp / "stack" / "tools.json"
        self.mine.parent.mkdir()
        self.mine.write_text(json.dumps({"$override": "../defs/tools.json", "tools": {}}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tools(self, *args, stdin="{}"):
        return subprocess.run([sys.executable, str(BIN)] + [str(a) for a in args], cwd=self.tmp,
                              env=env_helper.clean_env(drop=("TC_",)), capture_output=True, text=True, input=stdin)

    def ok(self, *args):
        r = self.run_tools(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def entry(self, name):
        return json.loads(self.mine.read_text())["tools"].get(name, "absent")

    def test_twice_counts_down_then_the_replaced_tool_comes_back(self):
        self.ok("--file", self.mine, "add", "--replace", "--uses", "2", "--name", "clock", "lib/clock")
        self.assertEqual(self.entry("clock")["uses"], 2)
        line = self.ok("--file", self.mine, "ls").stdout.splitlines()[0]
        self.assertTrue(line.startswith("clock\t") and line.endswith(" [uses left: 2]"), line)
        listed = json.loads(self.ok("--file", self.mine, "ls", "--json").stdout)[0]
        self.assertEqual(listed["uses"], 2)
        self.assertTrue(listed["tooldef"]["description"].endswith("(Taken off your tool list after 2 more successful calls.)"))
        self.assertEqual(self.ok("--file", self.mine, "call", "clock").stdout, "ok\n")      # the tool's own result passes through
        self.assertEqual(self.entry("clock")["uses"], 1)
        r = self.ok("--file", self.mine, "call", "clock")
        self.assertIn("tool clock is used up and was taken off the list", r.stderr)
        self.assertEqual(self.entry("clock"), "absent")
        listed = json.loads(self.ok("--file", self.mine, "ls", "--json").stdout)[0]      # the definition's clock again
        self.assertEqual(listed["path"], str(self.tmp / "lib" / "base_clock"))
        self.assertNotIn("uses", listed)

    def test_failed_calls_do_not_count_and_keep_the_exit_code(self):
        self.ok("--file", self.mine, "add", "--uses", "1", "lib/fails")
        r = self.run_tools("--file", self.mine, "call", "fails")
        self.assertEqual(r.returncode, 3)
        self.assertIn("boom", r.stderr)
        self.assertEqual(self.entry("fails")["uses"], 1)

    def test_uses_only_counted_in_the_given_registry_and_shapes(self):
        self.base.write_text(json.dumps({"tools": {"clock": {"path": "../lib/base_clock", "uses": 1}}}))
        r = self.run_tools("--file", self.mine, "call", "clock")
        self.assertEqual(r.returncode, 1)
        self.assertIn("RegistryBad", r.stderr)
        self.assertIn("counted down only in the registry given to aos-tools", r.stderr)
        for bad in ("0", "-1", "x", "1.5"):
            with self.subTest(uses=bad):
                r = self.run_tools("--file", self.mine, "add", "--uses", bad, "--name", "n%s" % abs(hash(bad)), "lib/clock")
                self.assertEqual(r.returncode, 1)
                self.assertIn("ArgumentsBad", r.stderr)
        self.mine.write_text(json.dumps({"tools": {"clock": {"path": "../lib/clock", "uses": 0}}}))
        r = self.run_tools("--file", self.mine, "ls")
        self.assertIn("RegistryBad", r.stderr)

    def test_replace_without_uses_drops_the_count(self):
        self.ok("--file", self.mine, "add", "--uses", "1", "--name", "extra", "lib/clock")
        self.ok("--file", self.mine, "add", "--replace", "--name", "extra", "lib/clock")
        self.assertNotIn("uses", self.entry("extra"))
        self.ok("--file", self.mine, "call", "extra")
        self.assertNotEqual(self.entry("extra"), "absent")


if __name__ == "__main__":
    unittest.main()
