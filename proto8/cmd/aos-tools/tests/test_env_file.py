"""Test aos-tools env_file (11-10 aos-tools-cli step 3): add --env-file stores only the location, call reads it every time, a missing file at call is PathMissing."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / "cmd" / "aos-tools" / "bin" / "aos-tools"

SHOW = """#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:] == ["--tooldef"]:
    print(json.dumps({"description": "show env", "env": ["TC_KEY"]}))
    sys.exit(0)
sys.stdin.read()
print(json.dumps({k: os.environ.get(k) for k in ("TC_KEY", "TC_OTHER", "TC_BOTH", "AOS_STACK")}))
"""


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and not k.startswith("TC_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class EnvFile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-envfile-"))
        self.proj = self.tmp / "proj"
        self.reg = self.proj / "tools.json"
        tool = self.proj / "bin" / "show"
        tool.parent.mkdir(parents=True)
        tool.write_text(SHOW)
        tool.chmod(0o755)
        self.secrets = self.proj / "secrets" / "s.env"
        self.secrets.parent.mkdir()
        self.secrets.write_text("TC_KEY=sk-first\nTC_BOTH=from-file\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tools(self, *args, cwd=None, **env):
        return subprocess.run([sys.executable, str(BIN)] + [str(a) for a in args], cwd=cwd or self.proj,
                              env=clean_env(**env), capture_output=True, text=True, input="{}")

    def ok(self, *args, **kw):
        r = self.run_tools(*args, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def call(self, **env):
        return json.loads(self.ok("--file", self.reg, "call", "show", **env).stdout)

    def add_relative(self, *extra):
        return self.ok("--file", "tools.json", "add", "--env-file", "secrets/s.env", *extra, "bin/show")

    def test_stores_location_not_content(self):
        r = self.add_relative()
        self.assertNotIn("warning", r.stderr)              # TC_KEY comes from the file: no hub warning
        text = self.reg.read_text()
        self.assertNotIn("sk-first", text)
        entry = json.loads(text)["tools"]["show"]
        self.assertEqual(entry, {"path": "bin/show", "env_file": "secrets/s.env"})

    def test_absolute_stays_absolute(self):
        self.ok("--file", self.reg, "add", "--env-file", self.secrets, self.proj / "bin" / "show")
        self.assertEqual(json.loads(self.reg.read_text())["tools"]["show"]["env_file"], str(self.secrets))

    def test_edit_takes_effect_next_call(self):
        self.add_relative()
        before = self.reg.read_bytes()
        self.assertEqual(self.call()["TC_KEY"], "sk-first")
        self.secrets.write_text("TC_KEY=sk-second\n")
        self.assertEqual(self.call()["TC_KEY"], "sk-second")
        self.assertEqual(self.reg.read_bytes(), before)

    def test_precedence(self):
        self.add_relative("--envs", "TC_BOTH=from-envs")
        out = self.call(TC_KEY="caller", TC_OTHER="caller", AOS_STACK=str(self.tmp / "st"))
        self.assertEqual(out["TC_KEY"], "sk-first")          # env_file beats the caller
        self.assertEqual(out["TC_OTHER"], "caller")          # untouched caller values stay
        self.assertEqual(out["TC_BOTH"], "from-envs")        # env beats env_file
        self.assertEqual(out["AOS_STACK"], os.path.join(str(self.tmp / "st"), "tools", "show", ""))

    def test_stack_cannot_be_overridden_by_file(self):
        self.secrets.write_text("AOS_STACK=/evil\nTC_KEY=x\n")
        self.add_relative()
        self.assertEqual(self.call(AOS_STACK=str(self.tmp / "st"))["AOS_STACK"],
                         os.path.join(str(self.tmp / "st"), "tools", "show", ""))

    def test_expands_with_call_environment(self):
        self.secrets.write_text('TC_KEY="${TC_BASE}/k"\n')
        self.ok("--file", "tools.json", "add", "--env-file", "secrets/s.env", "bin/show", TC_BASE="/at-add")
        self.assertEqual(self.call(TC_BASE="/at-call")["TC_KEY"], "/at-call/k")

    def test_moves_with_folder(self):
        self.add_relative()
        moved = self.tmp / "elsewhere"
        shutil.move(str(self.proj), str(moved))
        self.proj, self.reg = moved, moved / "tools.json"
        self.assertEqual(self.call()["TC_KEY"], "sk-first")

    def test_missing_at_add_warns_and_registers(self):
        self.secrets.unlink()
        r = self.add_relative()
        self.assertIn("aos-tools: warning: env file %s not found yet; registered anyway" % self.secrets, r.stderr)
        self.assertIn("tool show has unset hub variables: TC_KEY", r.stderr)
        self.assertEqual(json.loads(self.reg.read_text())["tools"]["show"]["env_file"], "secrets/s.env")
        self.ok("--file", self.reg, "ls")                    # ls does not read env files

    def test_missing_at_call_is_error(self):
        self.add_relative()
        self.secrets.unlink()
        r = self.run_tools("--file", self.reg, "call", "show")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertIn("aos-tools: error: PathMissing tool show: env file %s (from %s#/tools/show/env_file) does not exist"
                      % (self.secrets, self.reg), r.stderr)

    def test_bad_file_at_call(self):
        self.add_relative()
        self.secrets.write_text("not a line\n")
        r = self.run_tools("--file", self.reg, "call", "show")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-tools: error: DotenvBad tool show (from %s#/tools/show/env_file)" % self.reg, r.stderr)

    def test_bad_file_at_add(self):
        self.secrets.write_text("not a line\n")
        r = self.run_tools("--file", "tools.json", "add", "--env-file", "secrets/s.env", "bin/show")
        self.assertEqual(r.returncode, 1)
        self.assertIn("DotenvBad", r.stderr)
        self.assertFalse(self.reg.exists())

    def test_ls_long_shows_location_not_values(self):
        self.add_relative("--envs", "TC_OTHER=v")
        cols = self.ok("--file", self.reg, "ls", "-l").stdout.rstrip("\n").split("\t")
        self.assertEqual(cols[5], 'TC_OTHER,@"secrets/s.env"')
        self.assertNotIn("sk-first", self.ok("--file", self.reg, "ls", "--json").stdout)

    def test_directive_env_file(self):
        self.reg.write_text(json.dumps({"tools": {"show": {"path": "bin/show",
                                                           "env_file": {"$env": "TC_SECRETS", "$path": "/s.env"}}}}))
        self.assertEqual(self.call(TC_SECRETS=str(self.secrets.parent))["TC_KEY"], "sk-first")

    def test_bad_env_file_value(self):
        self.reg.write_text(json.dumps({"tools": {"show": {"path": "bin/show", "env_file": 3}}}))
        r = self.run_tools("--file", self.reg, "ls")
        self.assertEqual(r.returncode, 1)
        self.assertIn("RegistryBad", r.stderr)
        self.assertIn("env_file", r.stderr)


if __name__ == "__main__":
    unittest.main()
