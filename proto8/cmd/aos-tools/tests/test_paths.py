"""Test aos-tools path forms: overlay directives (path and env), add keeping the user's form, --path-json and --anchor."""
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
TOOL = PROTO / "lib" / "base" / "wall_clock"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class PathForms(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-paths-"))
        self.reg = self.tmp / "def" / "tools.json"
        self.over = self.tmp / "stack" / "tools.json"
        self.reg.parent.mkdir()
        self.over.parent.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tools(self, *args, cwd=None, **env):
        return subprocess.run([sys.executable, str(BIN)] + [str(a) for a in args], cwd=cwd or self.tmp,
                              env=clean_env(**env), capture_output=True, text=True)

    def ok(self, *args, **kw):
        r = self.run_tools(*args, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def stored(self, path, *keys):
        data = json.loads(Path(path).read_text())
        for k in keys:
            data = data[k]
        return data

    # ---- 1. overlay directives ----

    def test_overlay_env_path_resolved_each_time_and_not_written_back(self):
        self.over.write_text(json.dumps({"add": {"wc": {"path": {"$env": "TC_ROOT", "$path": "/lib/base/wall_clock"}}}}))
        before = self.over.read_text()
        r = self.ok("--file", self.reg, "--overlay", self.over, "ls", TC_ROOT=str(PROTO))
        self.assertIn("wc\tdir\t%s" % TOOL, r.stdout)
        # 換一份「proto8」：值跟著換（每次用到才解）
        other = self.tmp / "other"
        shutil.copytree(TOOL, other / "lib" / "base" / "wall_clock")
        r = self.ok("--file", self.reg, "--overlay", self.over, "ls", TC_ROOT=str(other))
        self.assertIn(str(other / "lib" / "base" / "wall_clock"), r.stdout)
        self.assertEqual(self.over.read_text(), before)

    def test_overlay_env_field_resolved(self):
        self.over.write_text(json.dumps({"add": {"wc": {"path": str(TOOL), "env": {"AOS_MEMORY": {"$env": "TC_KB"}}}}}))
        self.ok("--file", self.reg, "--overlay", self.over, "ls", TC_KB="/x/kb")

    def test_overlay_env_unset_names_file(self):
        self.over.write_text(json.dumps({"add": {"wc": {"path": {"$env": "TC_ROOT", "$path": "/lib/base/wall_clock"}}}}))
        r = self.run_tools("--file", self.reg, "--overlay", self.over, "ls")
        self.assertEqual(r.returncode, 1)
        self.assertIn("DirectiveBad", r.stderr)
        self.assertIn(str(self.over), r.stderr)
        self.assertIn("TC_ROOT", r.stderr)

    def test_missing_target_names_file_field_and_value(self):
        self.over.write_text(json.dumps({"add": {"wc": {"path": {"$env": "TC_ROOT", "$path": "/nowhere"}}}}))
        r = self.run_tools("--file", self.reg, "--overlay", self.over, "ls", TC_ROOT="/tmp/none-such")
        self.assertEqual(r.returncode, 1)
        self.assertIn("PathMissing", r.stderr)
        self.assertIn("#/add/wc/path", r.stderr)
        self.assertIn("/tmp/none-such/nowhere", r.stderr)

    def test_overlay_write_keeps_other_directives(self):
        self.over.write_text(json.dumps({"add": {"a": {"path": {"$env": "TC_ROOT", "$path": "/lib/base/wall_clock"}}}}))
        self.ok("--file", self.reg, "--overlay", self.over, "add", "-n", "b", TOOL, TC_ROOT=str(PROTO))
        self.assertEqual(self.stored(self.over, "add", "a", "path"), {"$env": "TC_ROOT", "$path": "/lib/base/wall_clock"})
        self.assertEqual(self.stored(self.over, "add", "b", "path"), str(TOOL))

    def test_overlay_plain_unchanged(self):
        self.over.write_text(json.dumps({"add": {"wc": {"path": os.path.relpath(TOOL, self.over.parent)}}, "rm": []}))
        r = self.ok("--file", self.reg, "--overlay", self.over, "ls")
        self.assertIn(str(TOOL), r.stdout)

    # ---- 8. add keeps the user's form ----

    def test_add_absolute_stores_absolute(self):
        self.ok("--file", self.reg, "add", TOOL)
        self.assertEqual(self.stored(self.reg, "tools", "wall_clock", "path"), str(TOOL))

    def test_add_relative_stores_relative_to_registry(self):
        work = self.tmp / "work"
        work.mkdir()
        rel = os.path.relpath(TOOL, work)
        self.ok("--file", self.reg, "add", rel, cwd=work)
        self.assertEqual(self.stored(self.reg, "tools", "wall_clock", "path"), os.path.relpath(TOOL, self.reg.parent))

    def test_add_relative_overlay_relative_to_overlay(self):
        self.ok("--file", self.reg, "--overlay", self.over, "add", os.path.relpath(TOOL, self.tmp))
        self.assertEqual(self.stored(self.over, "add", "wall_clock", "path"), os.path.relpath(TOOL, self.over.parent))
        self.assertFalse(os.path.lexists(self.over.parent / ".aos-proto8"))

    def test_add_no_auto_anchor_even_if_anchor_exists(self):
        os.symlink(PROTO, self.reg.parent / ".aos-proto8")
        self.ok("--file", self.reg, "add", TOOL)
        self.assertEqual(self.stored(self.reg, "tools", "wall_clock", "path"), str(TOOL))

    def test_add_path_json_stored_as_given(self):
        value = {"$env": "TC_ROOT", "$path": "/lib/base/wall_clock"}
        r = self.ok("--file", self.reg, "add", "--path-json", json.dumps(value), TC_ROOT=str(PROTO))
        self.assertIn("added wall_clock -> %s" % TOOL, r.stdout)
        self.assertEqual(self.stored(self.reg, "tools", "wall_clock", "path"), value)
        r = self.ok("--file", self.reg, "ls", TC_ROOT=str(PROTO))
        self.assertIn(str(TOOL), r.stdout)

    def test_add_path_json_relative_string_from_registry_dir(self):
        rel = os.path.relpath(TOOL, self.reg.parent)
        self.ok("--file", self.reg, "add", "--path-json", json.dumps(rel))
        self.assertEqual(self.stored(self.reg, "tools", "wall_clock", "path"), rel)

    def test_add_path_json_unset_env_fails_and_writes_nothing(self):
        r = self.run_tools("--file", self.reg, "add", "--path-json", '{"$env": "TC_ROOT", "$path": "/x"}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("DirectiveBad", r.stderr)
        self.assertFalse(self.reg.exists())

    def test_add_path_json_with_xxx_is_bad(self):
        r = self.run_tools("--file", self.reg, "add", "--path-json", '"x"', TOOL)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad", r.stderr)

    def test_add_anchor_when_asked(self):
        self.ok("--file", self.reg, "--overlay", self.over, "add", "--anchor", TOOL)
        self.assertEqual(self.stored(self.over, "add", "wall_clock", "path"), ".aos-proto8/lib/base/wall_clock")
        self.assertEqual(os.readlink(self.over.parent / ".aos-proto8"), str(PROTO))

    def test_add_anchor_keeps_users_relative_anchor(self):
        link = self.over.parent / ".aos-proto8"
        os.symlink(os.path.relpath(PROTO, self.over.parent), link)
        before = os.readlink(link)
        self.ok("--file", self.reg, "--overlay", self.over, "add", "--anchor", TOOL)
        self.assertEqual(os.readlink(link), before)

    def test_add_anchor_outside_repo_is_bad(self):
        outside = self.tmp / "t"
        shutil.copytree(TOOL, outside)
        r = self.run_tools("--file", self.reg, "add", "--anchor", outside)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad", r.stderr)


if __name__ == "__main__":
    unittest.main()
