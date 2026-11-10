"""knowledge_read（純 JSON 樹）：read／ls／find 在各種位置上的輸出、表與 not in index、$ref／$env、迴圈、錯誤代號。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / "_entry"


def write(path, value, raw=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(value if raw else json.dumps(value))


@unittest.skipUnless(shutil.which("aos-json"), "aos-json not on PATH")
class KnowledgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(os.path.realpath(self.tmp.name))
        self.root = base / "kb"
        self.outside = base / "outside.json"
        write(self.outside, {"inside": "outside value"})
        write(self.root / "_description.json", "aos in one page.")
        write(self.root / "_index.json", {
            "rules.json": {"_description": "Things you must never do.", "tags": ["core"]},
            "errors.json": {"_description": "How to read a failed call."},
            "cli/": {"_description": "Commands."},
            "../outside.json": {"_description": "Outside thing."},
            str(base / "outside.json") + "#/inside": {"_description": "Absolute inside."},
            "team": {"_description": "Team notes", "$env": "TEAM_KB", "$path": "/team.json"},
        })
        write(self.root / "rules.json", "Never rm -rf /.\nReally.")
        write(self.root / "errors.json", {
            "_description": "How to read a failed call: lines.",
            "_index": {"codes": {"_description": "What each Code ending means.", "tags": ["people"]},
                       "../rules.json": {"_description": "Back to the rules."}},
            "codes": "# Code endings\n\nLockFailed and friends.",
            "common": {"$ref": "far/common.json#/c"},
            "plain": {"a": 1, "b": [1, "two"]},
            "about": {"_description": "Only an intro, findme.", "k": "v"},
            "a/b": "slash key"})
        write(self.root / "far" / "common.json", {"c": {"x": "common LockFailed"}})
        write(self.root / "far" / "team.json", "Team text")
        write(self.root / "cli" / "_index.json", {})
        write(self.root / "cli" / "flags.json", {"flags": "--help"})
        write(self.root / "note.md", "plain text md\n", raw=True)
        write(self.root / "img.bin", b"\xff\xfe\x00")
        write(self.root / "_hidden.json", "hidden")
        self.env = {k: v for k, v in os.environ.items() if k not in ("AOS_CD", "TEAM_KB")}
        self.env.update(AOS_KNOWLEDGE=str(self.root), AOS_CD=str(ENTRY.parent))

    def run_tool(self, env=None, **args):
        return subprocess.run([sys.executable, str(ENTRY)], input=json.dumps(args), text=True,
                              capture_output=True, env=dict(self.env, **(env or {})), timeout=30)

    def ok(self, env=None, **args):
        r = self.run_tool(env, **args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout

    def fails(self, code, env=None, **args):
        r = self.run_tool(env, **args)
        self.assertEqual(r.returncode, 1, r.stdout)
        line = r.stderr.strip().splitlines()[-1]
        self.assertTrue(line.startswith("knowledge_read: error: %s " % code), line)
        self.assertEqual(r.stdout.strip(), line)
        return line

    def section(self, out, name):
        lines, keep = [], False
        for line in out.splitlines():
            if not line.startswith("  "):
                keep = line == name
            elif keep:
                lines.append(line[2:])
        return lines

    def test_root_read_intro_index_and_not_in_index(self):
        out = self.ok(op="read", env={"TEAM_KB": str(self.root / "far")})
        self.assertTrue(out.startswith("node: /\naos in one page.\n\nchildren:\n"), out)
        kids = self.section(out, "children:")
        self.assertEqual(kids[:3], ["rules.json  Things you must never do.", "errors.json  How to read a failed call.",
                                    "cli/  Commands."])
        self.assertEqual(kids[3], "%s  Outside thing." % self.outside)
        self.assertEqual(kids[4], "%s#/inside  Absolute inside." % self.outside)
        self.assertEqual(kids[5], "far/team.json  Team notes")
        self.assertEqual(self.section(out, "not in index:"), ["far/", "img.bin", "note.md"])

    def test_printed_paths_paste_back(self):
        out = self.ok(op="read", env={"TEAM_KB": str(self.root / "far")})
        for line in self.section(out, "children:") + self.section(out, "not in index:"):
            self.ok(op="read", path=line.split("  ")[0], env={"TEAM_KB": str(self.root / "far")})

    def test_env_cell_unset_is_noted_not_fatal(self):
        out = self.ok(op="ls")
        line = [l for l in self.section(out, "children:") if l.startswith("team")][0]
        self.assertIn("Team notes  [DirectiveBad", line)

    def test_object_with_index(self):
        out = self.ok(op="read", path="errors.json")
        self.assertTrue(out.startswith("node: errors.json\nHow to read a failed call: lines.\n\nchildren:\n"), out)
        self.assertEqual(self.section(out, "children:"),
                         ["errors.json#/codes  What each Code ending means.", "rules.json  Back to the rules."])
        self.assertEqual(self.section(out, "not in index:"),
                         ["errors.json#/common", "errors.json#/plain", "errors.json#/about", "errors.json#/a~1b"])

    def test_intro_only_object_and_folder_without_intro(self):
        self.assertEqual(self.ok(op="read", path="errors.json#/about"),
                         'node: errors.json#/about\n\nOnly an intro, findme.\n\n{\n  "k": "v"\n}\n')
        write(self.root / "far" / "only.json", {"_description": "Just this."})
        self.assertEqual(self.ok(op="read", path="far/only.json"), "node: far/only.json\n\nJust this.\n")
        out = self.ok(op="read", path="far/")                    # 沒有 _description.json＝只印表
        self.assertTrue(out.startswith("node: far/\nchildren: (none)\nnot in index:\n"), out)
        self.assertNotIn("_description", out)
        self.assertNotIn("_description", self.ok(op="read"))

    def test_find_hits_own_description(self):
        self.assertEqual(self.find(query="findme"), ["errors.json#/about  Only an intro, findme."])
        self.assertEqual(self.find(query="one page"), ["/  aos in one page."])
        self.assertEqual(self.find(query="failed call: lines"), ["errors.json  How to read a failed call.  [match: How to read a failed call: lines.]"])

    def test_string_is_raw_text(self):
        self.assertEqual(self.ok(op="read", path="errors.json#/codes"),
                         "node: errors.json#/codes\n\n# Code endings\n\nLockFailed and friends.\n")
        self.assertEqual(self.ok(op="read", path="rules.json"), "node: rules.json\n\nNever rm -rf /.\nReally.\n")
        self.assertIn("slash key", self.ok(op="read", path="errors.json#/a~1b"))

    def test_object_without_index_and_array(self):
        out = self.ok(op="read", path="errors.json#/plain")
        self.assertEqual(json.loads(out.split("\n", 2)[2]), {"a": 1, "b": [1, "two"]})
        self.assertEqual(self.ok(op="read", path="errors.json#/plain/b/1"), "node: errors.json#/plain/b/1\n\ntwo\n")
        ls = self.ok(op="ls", path="errors.json#/plain/b")
        self.assertIn("children: (none)", ls)
        self.assertEqual(self.section(ls, "not in index:"), ["errors.json#/plain/b/0", "errors.json#/plain/b/1"])

    def test_ref_content_is_resolved(self):
        out = self.ok(op="read", path="errors.json#/common")
        self.assertEqual(json.loads(out.split("\n", 2)[2]), {"x": "common LockFailed"})
        self.assertIn("common LockFailed", self.ok(op="read", path="errors.json#/common/x"))

    def test_folder_and_files(self):
        out = self.ok(op="ls", path="cli/")
        self.assertEqual(out, "node: cli/\nchildren: (none)\nnot in index:\n  cli/flags.json\n")
        self.assertEqual(self.ok(op="read", path="cli"), "node: cli/\nchildren: (none)\nnot in index:\n  cli/flags.json\n")
        self.assertEqual(self.ok(op="read", path="note.md"), "node: note.md\n\nplain text md\n")
        self.assertEqual(self.ok(op="read", path="img.bin"), "node: img.bin\n\nbinary file, 3 bytes\n")
        self.assertNotIn("_hidden", self.ok(op="ls"))
        self.assertIn("hidden", self.ok(op="read", path="_hidden.json"))   # 沒列也讀得到

    def test_relative_and_absolute_outside(self):
        self.assertIn("outside value", self.ok(op="read", path="../outside.json"))
        self.assertIn("outside value", self.ok(op="read", path=str(self.outside) + "#/inside"))

    def test_truncate(self):
        out = self.ok(op="read", path="errors.json#/codes", max_bytes=10)
        self.assertRegex(out, r"\n\[truncated: \d+ more bytes\]\n$")

    def find(self, **args):
        out = self.ok(op="find", **args)
        return self.section(out, "matches:")

    def test_find_query_tag_and_both(self):
        self.assertEqual(self.find(query="lockfailed"),
                         ["errors.json#/codes  What each Code ending means.  [match: LockFailed and friends.]",
                          "far/common.json#/c/x  [match: common LockFailed]"])   # 命中在內文＝附那一行
        self.assertEqual(self.find(tag="people"), ["errors.json#/codes  What each Code ending means."])
        self.assertEqual(self.find(tag="core", query="never"), ["rules.json  Things you must never do."])
        self.assertEqual(self.find(tag="core", query="lockfailed"), [])
        self.assertIn("matches: (none)", self.ok(op="find", query="zzz-nothing"))
        self.assertEqual(self.find(query="outside", path="cli/"), [])
        self.assertIn("%s  Outside thing." % self.outside, self.find(query="outside"))

    def test_missing_extension_hint(self):
        self.assertIn("(did you mean errors.json#/codes? keep the .json and put # before the key)",
                      self.fails("NodeMissing", op="read", path="errors/codes"))
        self.assertIn("(did you mean rules.json? keep the .json)", self.fails("NodeMissing", op="read", path="rules"))
        self.assertNotIn("did you mean", self.fails("NodeMissing", op="read", path="nope/x"))

    def test_find_snippet_long_line(self):
        write(self.root / "long.json", "a" * 300 + " needle " + "b" * 300)
        hit = self.find(query="NEEDLE", path="long.json")[0]
        self.assertRegex(hit, r"^long\.json  \[match: …a+ needle b+…\]$")
        self.assertLess(len(hit), 200)
        self.assertEqual(self.find(query="never"), ["rules.json  Things you must never do."])   # 命中在說明＝不附

    def test_find_env_cell_once(self):
        hits = self.find(query="team", env={"TEAM_KB": str(self.root / "far")})
        self.assertIn("far/team.json  Team notes", hits)

    def test_find_loops_do_not_hang(self):
        write(self.root / "loop" / "_index.json", {"./": {"_description": "me"}, "../loop/": {}, "../": {},
                                                   "a.json": {}})
        write(self.root / "loop" / "a.json", {"_index": {"..": {}, "x": {}, "../a.json": {}}, "x": "needle"})
        os.symlink(self.root / "loop", self.root / "loop" / "again")
        hits = self.find(query="needle", path="loop/")
        self.assertEqual(hits, ["loop/a.json#/x  [match: needle]"])

    def test_errors(self):
        self.fails("ArgumentsBad")
        self.fails("OpUnknown", op="cat")
        self.fails("ArgumentsBad", op="find")
        self.fails("ArgumentsBad", op="read", max_bytes=0)
        self.fails("PathBad", op="read", path="errors.json#codes")
        self.fails("PathBad", op="read", path="errors.json#/~2")
        line = self.fails("NodeMissing", op="read", path="errors.json#/nope")
        self.assertIn("errors.json has: errors.json#/codes", line)
        line = self.fails("NodeMissing", op="read", path="nope.json")
        self.assertIn("/ has: cli/, errors.json", line)
        self.assertIn("drop the leading /", self.fails("NodeMissing", op="read", path="/rules.json"))
        self.assertIn("file.json#/key", self.fails("NodeMissing", op="read", path="errors.json/codes"))
        self.fails("TargetBad", op="ls", path="rules.json")
        self.fails("TargetBad", op="read", path="note.md#/x")
        self.fails("TargetBad", op="read", path="cli/#/x")
        write(self.root / "bad.json", "{not json", raw=True)
        self.fails("FileBad", op="read", path="bad.json")
        write(self.root / "dangling.json", {"r": {"$ref": "missing.json"}})
        self.fails("DirectiveBad", op="read", path="dangling.json")
        self.fails("KnowledgeMissing", env={"AOS_KNOWLEDGE": ""}, op="read")
        empty = Path(self.tmp.name) / "emptybin"
        empty.mkdir()
        self.fails("LaunchFailed", env={"PATH": str(empty)}, op="read")

    def test_root_flag_and_no_default(self):
        """庫根：--root DIR ＞ _knowledge.json ＞ AOS_KNOWLEDGE；都沒給＝KnowledgeMissing 教三種給法（11-10 深夜：工具沒有內建預設）。"""
        line = self.fails("KnowledgeMissing", env={"AOS_KNOWLEDGE": ""}, op="read")
        for how in ("--root DIR", "_knowledge.json", "AOS_KNOWLEDGE"):
            self.assertIn(how, line)
        other = Path(self.tmp.name) / "other"
        write(other / "_description.json", "other kb.")
        write(other / "_index.json", {})
        def run(argv, env=None, cwd=None):
            return subprocess.run([sys.executable, str(ENTRY)] + argv, input='{"op": "read"}', text=True, capture_output=True,
                                  env=dict(self.env, **(env or {})), cwd=cwd, timeout=30)
        r = run(["--root", str(other)])                     # 旗標蓋過 AOS_KNOWLEDGE
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("other kb.", r.stdout)
        r = run(["--root=other"], env={"AOS_KNOWLEDGE": "", "AOS_WS": self.tmp.name})   # 相對從 $AOS_WS
        self.assertIn("other kb.", r.stdout)
        r = run(["--root", "other"], env={"AOS_KNOWLEDGE": "", "AOS_WS": ""}, cwd=self.tmp.name)   # 沒 WS＝cwd
        self.assertIn("other kb.", r.stdout)
        r = run(["--root", str(other / "nope")])
        self.assertIn("knowledge_read: error: KnowledgeBad --root", r.stdout)
        for argv in (["--root"], ["--root", str(other), "--root", str(other)], ["--root="]):
            r = run(argv)
            self.assertEqual(r.returncode, 1)
            self.assertIn("knowledge_read: error: ArgumentsBad --root", r.stdout)
        r = run(["--root", str(other), "--help"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage: knowledge_read [--root DIR]", r.stdout)
        r = subprocess.run([sys.executable, str(ENTRY)], input=json.dumps({"op": "read", "root": str(other)}), text=True,
                           capture_output=True, env=self.env, timeout=30)
        self.assertIn("ArgumentsBad", r.stdout)             # 腦給的 JSON 改不了庫根

    def test_help_is_english(self):
        r = subprocess.run([sys.executable, str(ENTRY), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage: knowledge_read", r.stdout)
        self.assertTrue(r.stdout.isascii(), r.stdout)


if __name__ == "__main__":
    unittest.main()
