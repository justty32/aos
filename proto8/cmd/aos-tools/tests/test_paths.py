"""Test aos-tools path forms: directives in an overriding registry (path and env), add keeping the user's form, --path-json, and the PathMissing line."""
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

    def over_with(self, tools):
        if not self.reg.exists():
            self.reg.write_text(json.dumps({"tools": {}}))
        self.over.write_text(json.dumps({"$override": "../def/tools.json", "tools": tools}))

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

    # ---- 1. directives in a file that overrides another ----

    def test_overlay_env_path_resolved_each_time_and_not_written_back(self):
        self.over_with({"wc": {"path": {"$env": "TC_ROOT", "$path": "/lib/base/peek_now_time"}}})
        before = self.over.read_text()
        r = self.ok("--file", self.over, "ls", "-l", TC_ROOT=str(PROTO))
        self.assertIn("wc\tdir\t%s" % TOOL, r.stdout)
        # 換一份「proto8」：值跟著換（每次用到才解）
        other = self.tmp / "other"
        shutil.copytree(TOOL, other / "lib" / "base" / "peek_now_time")
        r = self.ok("--file", self.over, "ls", "-l", TC_ROOT=str(other))
        self.assertIn(str(other / "lib" / "base" / "peek_now_time"), r.stdout)
        self.assertEqual(self.over.read_text(), before)

    def test_override_ref_hash_takes_the_file_itself(self):
        """11-12 ref-hash：$override 的指示詞寫 {"$ref": "#/…"}＝這份登記檔自己。"""
        self.reg.write_text(json.dumps({"tools": {"wc": {"path": str(TOOL)}}}))
        self.over.write_text(json.dumps({"bases": {"def": "../def/tools.json"}, "$override": {"$ref": "#/bases/def"}, "tools": {}}))
        r = self.ok("--file", self.over, "ls", "-l")
        self.assertIn("wc\tdir\t%s" % TOOL, r.stdout)

    def test_overlay_env_field_resolved(self):
        self.over_with({"wc": {"path": str(TOOL), "env": {"MY_DIR": {"$env": "TC_KB"}}}})
        self.ok("--file", self.over, "ls", TC_KB="/x/kb")

    def test_overlay_env_unset_names_file(self):
        self.over_with({"wc": {"path": {"$env": "TC_ROOT", "$path": "/lib/base/peek_now_time"}}})
        r = self.run_tools("--file", self.over, "ls")
        self.assertEqual(r.returncode, 1)
        self.assertIn("DirectiveBad", r.stderr)
        self.assertIn(str(self.over), r.stderr)
        self.assertIn("TC_ROOT", r.stderr)

    def test_missing_target_names_file_field_and_value(self):
        self.over_with({"wc": {"path": {"$env": "TC_ROOT", "$path": "/nowhere"}}})
        r = self.run_tools("--file", self.over, "ls", TC_ROOT="/tmp/none-such")
        self.assertEqual(r.returncode, 0, r.stderr)    # 11-12 tool-path-broken：ls 略過壞的那支、提醒一行；完整原因看 get
        self.assertIn("warning: tool wc skipped: PathMissing", r.stderr)
        r = self.run_tools("--file", self.over, "get", "wc", TC_ROOT="/tmp/none-such")
        self.assertEqual(r.returncode, 1)
        self.assertIn("PathMissing", r.stderr)
        self.assertIn("#/tools/wc/path", r.stderr)
        self.assertIn("/tmp/none-such/nowhere", r.stderr)

    def test_overlay_write_keeps_other_directives(self):
        self.over_with({"a": {"path": {"$env": "TC_ROOT", "$path": "/lib/base/peek_now_time"}}})
        self.ok("--file", self.over, "add", "-n", "b", TOOL, TC_ROOT=str(PROTO))
        self.assertEqual(self.stored(self.over, "tools", "a", "path"), {"$env": "TC_ROOT", "$path": "/lib/base/peek_now_time"})
        self.assertEqual(self.stored(self.over, "tools", "b", "path"), str(TOOL))

    def test_overlay_plain_unchanged(self):
        self.over_with({"wc": {"path": os.path.relpath(TOOL, self.over.parent)}})
        r = self.ok("--file", self.over, "ls", "-l")
        self.assertIn(str(TOOL), r.stdout)

    # ---- 8. add keeps the user's form ----

    def test_add_absolute_stores_absolute(self):
        self.ok("--file", self.reg, "add", TOOL)
        self.assertEqual(self.stored(self.reg, "tools", "peek_now_time", "path"), str(TOOL))

    def test_add_relative_stores_relative_to_registry(self):
        work = self.tmp / "work"
        work.mkdir()
        rel = os.path.relpath(TOOL, work)
        self.ok("--file", self.reg, "add", rel, cwd=work)
        self.assertEqual(self.stored(self.reg, "tools", "peek_now_time", "path"), os.path.relpath(TOOL, self.reg.parent))

    def test_add_relative_overlay_relative_to_overlay(self):
        self.over_with({})
        self.ok("--file", self.over, "add", os.path.relpath(TOOL, self.tmp))
        self.assertEqual(self.stored(self.over, "tools", "peek_now_time", "path"), os.path.relpath(TOOL, self.over.parent))

    def test_add_path_json_stored_as_given(self):
        value = {"$env": "TC_ROOT", "$path": "/lib/base/peek_now_time"}
        r = self.ok("--file", self.reg, "add", "--path-json", json.dumps(value), TC_ROOT=str(PROTO))
        self.assertIn("added peek_now_time -> %s" % TOOL, r.stdout)
        self.assertEqual(self.stored(self.reg, "tools", "peek_now_time", "path"), value)
        r = self.ok("--file", self.reg, "ls", "-l", TC_ROOT=str(PROTO))
        self.assertIn(str(TOOL), r.stdout)

    def test_add_path_json_relative_string_from_registry_dir(self):
        rel = os.path.relpath(TOOL, self.reg.parent)
        self.ok("--file", self.reg, "add", "--path-json", json.dumps(rel))
        self.assertEqual(self.stored(self.reg, "tools", "peek_now_time", "path"), rel)

    def test_add_path_json_unset_env_fails_and_writes_nothing(self):
        r = self.run_tools("--file", self.reg, "add", "--path-json", '{"$env": "TC_ROOT", "$path": "/x"}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("DirectiveBad", r.stderr)
        self.assertFalse(self.reg.exists())

    def test_add_path_json_with_xxx_is_bad(self):
        r = self.run_tools("--file", self.reg, "add", "--path-json", '"x"', TOOL)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad", r.stderr)

    def test_missing_path_names_file_cell_and_resolved_path(self):
        self.reg.write_text(json.dumps({"tools": {"gone": {"path": "nowhere/gone"}}}), encoding="utf-8")
        r = self.run_tools("--file", self.reg, "ls")
        self.assertEqual(r.returncode, 0, r.stderr)    # 11-12 tool-path-broken：ls 略過壞的那支；get 照舊報原錯
        self.assertIn("gone\tbroken: PathMissing", r.stdout)
        r = self.run_tools("--file", self.reg, "get", "gone")
        self.assertEqual(r.returncode, 1)
        self.assertIn("PathMissing", r.stderr)
        self.assertIn("%s#/tools/gone/path" % self.reg, r.stderr)
        self.assertIn(str(self.reg.parent / "nowhere" / "gone"), r.stderr)


if __name__ == "__main__":
    unittest.main()
