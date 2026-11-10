"""Test aos-tools "$override" registries (11-10 aos-tools-cli step 4): patch merge with null removal, chains and arrays, loops and diamonds, writes only to F, the override subcommand."""
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
KEY = "$override"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and not k.startswith("TC_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


class Override(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aos-tools-override-"))
        self.defs = self.tmp / "defs"
        self.stack = self.tmp / "stack"
        self.defs.mkdir()
        self.stack.mkdir()
        for n in ("a", "b", "c"):
            shutil.copytree(TOOL, self.defs / "lib" / n)
        self.base = self.defs / "tools.json"
        self.write(self.base, {"tools": {"a": {"path": "lib/a", "env": {"K1": "base", "K2": "base"}},
                                         "b": {"path": "lib/b"}}})
        self.mine = self.stack / "tools.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, p, obj):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj))

    def run_tools(self, *args, **env):
        return subprocess.run([sys.executable, str(BIN)] + [str(a) for a in args], cwd=self.tmp,
                              env=clean_env(**env), capture_output=True, text=True, input="{}")

    def ok(self, *args, **env):
        r = self.run_tools(*args, **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def bad(self, code, *args, **env):
        r = self.run_tools(*args, **env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("aos-tools: error: %s " % code, r.stderr)
        return r

    def names(self, f):
        return [line.split("\t")[0] for line in self.ok("--file", f, "ls").stdout.splitlines()]

    def listed(self, f):
        return {t["name"]: t for t in json.loads(self.ok("--file", f, "ls", "--json").stdout)}

    def long(self, f):
        return {c[0]: c for c in (line.split("\t") for line in self.ok("--file", f, "ls", "-l").stdout.splitlines())}

    # ---- shape and merge ----

    def test_one_level_add_and_null(self):
        self.write(self.mine, {KEY: "../defs/tools.json", "tools": {"c": {"path": "../defs/lib/c"}, "b": None}})
        self.assertEqual(self.names(self.mine), ["a", "c"])

    def test_long_shows_null_rows(self):
        """11-10 晚使用者「3.顯示」：ls -l 列出被 null 關掉的名字＋它蓋掉的那支；一般 ls 不列。"""
        self.write(self.mine, {KEY: "../defs/tools.json", "tools": {"b": None, "zz": None}})
        self.assertNotIn("b", self.names(self.mine))
        t = self.long(self.mine)
        self.assertEqual(t["b"][1:], ["null", str(self.defs / "lib" / "b"), "%s#/tools/b" % self.mine, "null", "-"])
        self.assertEqual(t["zz"][1:3], ["null", "-"])                 # 底檔沒有的名字：PATH＝-

    def test_null_in_plain_registry_is_absent(self):
        self.write(self.mine, {"tools": {"a": {"path": "../defs/lib/a", "env": None}, "gone": None}})
        self.assertEqual(self.names(self.mine), ["a"])

    def test_partial_entry_keeps_base_env(self):
        self.write(self.mine, {KEY: "../defs/tools.json", "tools": {"a": {"env": {"K2": "mine", "K1": None}}}})
        cols = self.long(self.mine)["a"]
        self.assertEqual(cols[2], str(self.defs / "lib" / "a"))
        self.assertEqual(cols[3], "%s#/tools/a" % self.base)        # FROM = where the path comes from
        self.assertEqual(cols[5], "K2")

    def test_replace_writes_null_for_base_keys(self):
        self.ok("--file", self.mine, "override", self.base)
        self.ok("--file", self.mine, "add", "--replace", "-n", "a", self.defs / "lib" / "c")
        entry = json.loads(self.mine.read_text())["tools"]["a"]
        self.assertEqual(entry, {"path": str(self.defs / "lib" / "c"), "env": None})
        self.assertEqual(self.long(self.mine)["a"][5], "-")

    def test_without_replace_is_tool_exists(self):
        self.ok("--file", self.mine, "override", self.base)
        r = self.bad("ToolExists", "--file", self.mine, "add", "-n", "a", self.defs / "lib" / "c")
        self.assertIn("add --replace to replace it", r.stderr)
        self.bad("FlagUnknown", "--file", self.mine, "add", "--override", "-n", "a", self.defs / "lib" / "c")

    def test_two_level_chain(self):
        mid = self.tmp / "mid" / "tools.json"
        self.write(mid, {KEY: "../defs/tools.json", "tools": {"b": None, "c": {"path": "../defs/lib/c"}}})
        self.write(self.mine, {KEY: "../mid/tools.json", "tools": {"b": {"path": "../defs/lib/b"}}})
        self.assertEqual(self.names(self.mine), ["a", "b", "c"])
        self.assertEqual(self.long(self.mine)["b"][3], "%s#/tools/b" % self.mine)
        self.assertEqual(self.long(self.mine)["c"][3], "%s#/tools/c" % mid)

    def test_array_in_order_later_wins(self):
        other = self.tmp / "other" / "tools.json"
        self.write(other, {"tools": {"a": {"path": "../defs/lib/c", "env": {"K3": "o"}}, "b": None}})
        self.write(self.mine, {KEY: ["../defs/tools.json", "../other/tools.json"], "tools": {}})
        t = self.long(self.mine)
        self.assertEqual(sorted(n for n, c in t.items() if c[1] != "null"), ["a"])   # one ordered sequence: the later base's null covers b
        self.assertEqual(t["b"][1:4], ["null", str(self.defs / "lib" / "b"), "%s#/tools/b" % other])   # ls -l shows what it hides
        self.assertEqual(t["a"][2], str(self.defs / "lib" / "c"))
        self.assertEqual(t["a"][3], "%s#/tools/a" % other)
        self.assertEqual(t["a"][5], "K1,K2,K3")                   # patch merge: env keys from both

    def test_array_null_in_f_removes(self):
        other = self.tmp / "other" / "tools.json"
        self.write(other, {"tools": {"c": {"path": "../defs/lib/c"}}})
        self.write(self.mine, {KEY: ["../defs/tools.json", "../other/tools.json"], "tools": {"a": None, "c": None}})
        self.assertEqual(self.names(self.mine), ["b"])

    def test_empty_array_is_no_base(self):
        self.write(self.mine, {KEY: [], "tools": {"c": {"path": "../defs/lib/c"}}})
        self.assertEqual(self.names(self.mine), ["c"])

    def test_diamond_is_not_a_loop(self):
        left, right = self.tmp / "l" / "tools.json", self.tmp / "r" / "tools.json"
        self.write(left, {KEY: "../defs/tools.json", "tools": {"c": {"path": "../defs/lib/c"}}})
        self.write(right, {KEY: "../defs/tools.json", "tools": {"a": None}})
        self.write(self.mine, {KEY: ["../l/tools.json", "../r/tools.json"], "tools": {}})
        # sequence = defs, l, defs, r, mine: defs twice is not a loop; r's null covers a last
        self.assertEqual(self.names(self.mine), ["b", "c"])

    def test_dict_after_null_starts_fresh(self):
        other = self.tmp / "other" / "tools.json"
        self.write(other, {"tools": {"a": None}})
        self.write(self.mine, {KEY: ["../defs/tools.json", "../other/tools.json"],
                               "tools": {"a": {"path": "../defs/lib/c"}}})
        cols = self.long(self.mine)["a"]
        self.assertEqual(cols[2], str(self.defs / "lib" / "c"))
        self.assertEqual(cols[5], "-")                            # env from defs was covered by null, not merged back

    def test_null_field_is_unset(self):
        self.write(self.mine, {KEY: "../defs/tools.json", "tools": {"a": {"env": {"K1": None}}}})
        self.assertEqual(self.long(self.mine)["a"][5], "K2")
        self.write(self.mine, {KEY: "../defs/tools.json", "tools": {"a": {"env": None}}})
        self.assertEqual(self.long(self.mine)["a"][5], "-")

    def test_loop_is_registry_bad(self):
        other = self.tmp / "other" / "tools.json"
        self.write(other, {KEY: "../stack/tools.json", "tools": {}})
        self.write(self.mine, {KEY: "../other/tools.json", "tools": {}})
        r = self.bad("RegistryBad", "--file", self.mine, "ls")
        self.assertIn("$override chain loops: %s -> %s -> %s" % (self.mine, other, self.mine), r.stderr)

    def test_loop_through_array_branch(self):
        other = self.tmp / "other" / "tools.json"
        self.write(other, {KEY: ["../defs/tools.json", "../stack/tools.json"], "tools": {}})
        self.write(self.mine, {KEY: ["../defs/tools.json", "../other/tools.json"], "tools": {}})
        self.assertIn("chain loops", self.bad("RegistryBad", "--file", self.mine, "ls").stderr)

    def test_self_loop(self):
        self.write(self.mine, {KEY: "tools.json", "tools": {}})
        self.bad("RegistryBad", "--file", self.mine, "ls")

    # ---- pointer errors ----

    def test_missing_base(self):
        self.write(self.mine, {KEY: "../nowhere.json", "tools": {}})
        r = self.bad("PathMissing", "--file", self.mine, "ls")
        self.assertIn("%s#/$override: %s does not exist" % (self.mine, self.tmp / "nowhere.json"), r.stderr)

    def test_missing_array_element_names_index(self):
        self.write(self.mine, {KEY: ["../defs/tools.json", "../nowhere.json"], "tools": {}})
        self.assertIn("#/$override/1:", self.bad("PathMissing", "--file", self.mine, "ls").stderr)

    def test_base_not_object(self):
        p = self.tmp / "arr.json"
        p.write_text("[1]")
        self.write(self.mine, {KEY: "../arr.json", "tools": {}})
        r = self.bad("RegistryBad", "--file", self.mine, "ls")
        self.assertIn("(from %s#/$override)" % self.mine, r.stderr)

    def test_element_not_a_path(self):
        self.write(self.mine, {KEY: ["../defs/tools.json", 3], "tools": {}})
        self.assertIn("#/$override/1 must be a path", self.bad("RegistryBad", "--file", self.mine, "ls").stderr)

    def test_base_without_tools_is_empty(self):
        p = self.tmp / "empty.json"
        p.write_text("{}")
        self.write(self.mine, {KEY: "../empty.json", "tools": {"c": {"path": "../defs/lib/c"}}})
        self.assertEqual(self.names(self.mine), ["c"])

    def test_add_rm_keys_are_registry_bad(self):
        self.write(self.mine, {"add": {"c": {"path": "../defs/lib/c"}}})
        self.assertIn("top-level add / rm", self.bad("RegistryBad", "--file", self.mine, "ls").stderr)

    def test_env_pointer_resolved_each_time(self):
        self.write(self.mine, {KEY: {"$env": "TC_DEFS", "$path": "/tools.json"}, "tools": {}})
        self.assertEqual(self.names(self.mine) if False else
                         [l.split("\t")[0] for l in self.ok("--file", self.mine, "ls", TC_DEFS=str(self.defs)).stdout.splitlines()],
                         ["a", "b"])
        moved = self.tmp / "defs2"
        shutil.move(str(self.defs), str(moved))
        r = self.ok("--file", self.mine, "ls", TC_DEFS=str(moved))
        self.assertIn(str(moved / "lib" / "a"), r.stdout)
        self.bad("DirectiveBad", "--file", self.mine, "ls")

    def test_relative_pointer_moves_with_tree(self):
        self.ok("--file", self.mine, "override", self.base.relative_to(self.tmp))
        self.assertEqual(json.loads(self.mine.read_text())[KEY], "../defs/tools.json")
        moved = self.tmp / "moved"
        moved.mkdir()
        shutil.move(str(self.defs), str(moved / "defs"))
        shutil.move(str(self.stack), str(moved / "stack"))
        self.assertIn(str(moved / "defs" / "lib" / "a"), self.ok("--file", moved / "stack" / "tools.json", "ls").stdout)

    # ---- writes go only to F ----

    def test_add_rm_leave_base_bytes(self):
        before = self.base.read_bytes()
        self.ok("--file", self.mine, "override", self.base)
        self.ok("--file", self.mine, "add", self.defs / "lib" / "c")
        r = self.ok("--file", self.mine, "rm", "a")
        self.assertEqual(r.stdout, "removed a (%s: set to null over %s)\n" % (self.mine, self.base))
        self.ok("--file", self.mine, "rm", "c")
        self.assertEqual(self.base.read_bytes(), before)
        data = json.loads(self.mine.read_text())
        self.assertEqual(data["tools"], {"a": None})
        self.assertEqual(self.names(self.mine), ["b"])

    def test_rm_base_then_add_back(self):
        self.ok("--file", self.mine, "override", self.base)
        self.ok("--file", self.mine, "rm", "a")
        self.ok("--file", self.mine, "add", "-n", "a", self.defs / "lib" / "a")
        self.assertEqual(self.names(self.mine), ["a", "b"])
        self.assertEqual(json.loads(self.mine.read_text())["tools"]["a"]["env"], None)   # re-added as given, base env not inherited

    def test_new_base_tool_shows_through(self):
        self.ok("--file", self.mine, "override", self.base)
        self.ok("--file", self.base, "add", self.defs / "lib" / "c")
        self.assertEqual(self.names(self.mine), ["a", "b", "c"])

    # ---- the override subcommand ----

    def test_override_creates_file(self):
        r = self.ok("--file", self.mine, "override", self.base)
        self.assertEqual(r.stdout, "%s $override -> %s\n" % (self.mine, json.dumps(str(self.base))))
        self.assertEqual(json.loads(self.mine.read_text()), {KEY: str(self.base), "tools": {}})

    def test_override_many_bases_and_repoint(self):
        other = self.tmp / "other" / "tools.json"
        self.write(other, {"tools": {"c": {"path": "../defs/lib/c"}}})
        self.ok("--file", self.mine, "override", self.base, "other/tools.json")
        self.assertEqual(json.loads(self.mine.read_text())[KEY], [str(self.base), "../other/tools.json"])
        self.assertEqual(self.names(self.mine), ["a", "b", "c"])
        self.ok("--file", self.mine, "rm", "a")
        self.ok("--file", self.mine, "override", "other/tools.json")
        data = json.loads(self.mine.read_text())
        self.assertEqual(data, {KEY: "../other/tools.json", "tools": {"a": None}})

    def test_override_path_json(self):
        value = {"$env": "TC_DEFS", "$path": "/tools.json"}
        self.ok("--file", self.mine, "override", "--path-json", json.dumps(value), TC_DEFS=str(self.defs))
        self.assertEqual(json.loads(self.mine.read_text())[KEY], value)

    def test_override_refuses_plain_registry_with_tools(self):
        before = self.base.read_bytes()
        self.bad("RegistryBad", "--file", self.base, "override", self.mine)
        self.assertEqual(self.base.read_bytes(), before)

    def test_override_checks_before_writing(self):
        self.bad("PathMissing", "--file", self.mine, "override", "nowhere.json")
        self.assertFalse(self.mine.exists())
        self.write(self.mine, {KEY: str(self.base), "tools": {}})
        before = self.mine.read_bytes()
        x = self.base.parent / "x.json"
        self.write(x, {"tools": {}})
        self.bad("RegistryBad", "--file", x, "override", x)
        self.assertEqual(json.loads(x.read_text()), {"tools": {}})
        self.assertEqual(self.mine.read_bytes(), before)

    def test_override_needs_base(self):
        self.bad("ArgumentsBad", "--file", self.mine, "override")

    def test_ref_tools_still_work_with_override(self):
        part = self.stack / "part.json"
        self.write(part, {"c": {"path": "../defs/lib/c"}, "a": None})
        self.write(self.mine, {KEY: "../defs/tools.json", "tools": {"$ref": ["part.json"]}})
        self.assertEqual(self.names(self.mine), ["b", "c"])


if __name__ == "__main__":
    unittest.main()
