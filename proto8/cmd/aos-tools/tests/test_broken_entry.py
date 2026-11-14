"""Test one broken registry entry (path gone, definition missing or bad) is skipped by ls with a warning while the others list and call as usual, and get / call on it still fail with its own error (11-12 tool-path-broken)."""
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
TOOL = PROTO / "lib" / "base" / "peek_now_time"


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class BrokenEntry(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-broken-"))
        shutil.copytree(TOOL, self.tmp / "tools" / "clock")
        shutil.copytree(TOOL, self.tmp / "tools" / "aos_cache")
        (self.tmp / "tools" / "empty").mkdir()            # 一個沒有 _tooldef 的資料夾（ToolDefMissing）
        self.reg = self.tmp / "tools.json"
        self.reg.write_text(json.dumps({"tools": {"clock": {"path": "tools/clock"},
                                                  "aos_cache": {"path": "tools/aos_cache"}}}))
        (self.tmp / "new_tools").mkdir()
        (self.tmp / "tools" / "aos_cache").rename(self.tmp / "new_tools" / "aos_cache")   # 搬走了、登記還記舊路徑

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tools(self, *args):
        return subprocess.run([sys.executable, str(BIN), "--file", str(self.reg)] + list(args), cwd=self.tmp,
                              env=clean_env(), capture_output=True, text=True, input="")

    def test_ls_skips_the_broken_one(self):
        r = self.run_tools("ls")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual([l.split("\t")[0] for l in lines], ["aos_cache", "clock"])
        self.assertTrue(lines[0].startswith("aos_cache\tbroken: PathMissing (its path does not exist)"), lines[0])
        self.assertIn("rm aos_cache", lines[0])
        warns = [l for l in r.stderr.splitlines() if l]
        self.assertEqual(len(warns), 1, r.stderr)
        self.assertTrue(warns[0].startswith("aos-tools: warning: tool aos_cache skipped: PathMissing"), warns[0])
        self.assertNotIn(str(self.tmp), warns[0])          # 不帶絕對路徑
        self.assertNotIn("error:", r.stderr)

    def test_long_and_json(self):
        r = self.run_tools("ls", "-l")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = {l.split("\t")[0]: l.split("\t") for l in r.stdout.splitlines()}
        self.assertEqual(rows["aos_cache"][1:3], ["broken", str(self.tmp / "tools" / "aos_cache")])
        self.assertEqual(rows["aos_cache"][4], '"tools/aos_cache"')
        self.assertEqual(rows["clock"][1], "dir")
        r = self.run_tools("ls", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([t["name"] for t in json.loads(r.stdout)], ["clock"])
        self.assertIn("warning: tool aos_cache skipped", r.stderr)

    def test_others_still_get_and_call(self):
        r = self.run_tools("get", "clock")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_tools("call", "clock", "{}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"^\d{4}-\d\d-\d\dT")

    def test_the_broken_one_keeps_its_error(self):
        for args in (("get", "aos_cache"), ("call", "aos_cache", "{}")):
            r = self.run_tools(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("aos-tools: error: PathMissing tool aos_cache", r.stderr, args)

    def test_rm_then_add_the_moved_path(self):
        r = self.run_tools("rm", "aos_cache")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_tools("add", "new_tools/aos_cache")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_tools("ls")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertNotIn("broken", r.stdout)

    def test_missing_definition_is_skipped_too(self):
        data = json.loads(self.reg.read_text())
        data["tools"]["aos_cache"]["path"] = "new_tools/aos_cache"
        data["tools"]["empty"] = {"path": "tools/empty"}
        self.reg.write_text(json.dumps(data))
        r = self.run_tools("ls")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("empty\tbroken: ToolDefMissing (no tool definition there)", r.stdout)
        self.assertIn("aos_cache\tGet the current time", r.stdout)

    def test_registry_itself_broken_is_still_an_error(self):
        self.reg.write_text("{not json")
        r = self.run_tools("ls")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-tools: error: RegistryBad", r.stderr)


if __name__ == "__main__":
    unittest.main()
