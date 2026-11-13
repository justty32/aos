"""Test aos-json-view: text blocks (newlines and string arrays), compact inline objects/arrays, key alignment, wrapping by display width, $ref, control characters, pointers, colour and errors."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "aos-json-view")
_loader = importlib.machinery.SourceFileLoader("aos_json_view", BIN)
_spec = importlib.util.spec_from_loader("aos_json_view", _loader)
jv = importlib.util.module_from_spec(_spec)
_loader.exec_module(jv)


def view(v, width=60, color=False):
    return jv.View(width, color).render(v)


def run(*args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    env.pop("NO_COLOR", None)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, BIN, *args], capture_output=True, text=True, env=env)


class Render(unittest.TestCase):
    def test_newline_in_string_breaks_line(self):
        self.assertEqual(view({"a": "one\ntwo"}), "a:\n  one\n  two\n")

    def test_string_array_is_text_block(self):
        out = view({"d": ["# Title", "", "Body line."]})
        self.assertEqual(out, "d:\n  # Title\n\n  Body line.\n")

    def test_short_containers_inline_and_keys_aligned(self):
        out = view({"name": "x", "n": 3, "tags": ["a", "b"], "o": {"k": True, "z": None}})
        self.assertEqual(out, "name: x\nn:    3\ntags: [a, b]\no:    {k: true, z: null}\n")

    def test_long_array_uses_dashes(self):
        out = view({"items": [{"name": "alpha", "role": "r" * 50}, {"name": "beta", "role": "s"}]}, width=50)
        self.assertIn("items:\n  - name: alpha\n    role: ", out)
        self.assertIn("  - {name: beta, role: s}", out)

    def test_wrap_counts_wide_chars(self):
        out = view({"k": "字" * 30}, width=30)
        for line in out.splitlines():
            self.assertLessEqual(jv.dw(line), 30)
        self.assertEqual(len(out.splitlines()), 3)
        self.assertTrue(out.splitlines()[1].startswith("   字"))   # continuation aligned with the value

    def test_text_block_continuation_hangs(self):
        out = view({"t": ["word " * 20, "next"]}, width=40)
        lines = out.splitlines()
        self.assertTrue(lines[1].startswith("  word"))
        self.assertTrue(lines[2].startswith("    word"))
        self.assertEqual(lines[-1], "  next")

    def test_ref_shown_not_followed(self):
        self.assertEqual(view({"$ref": "other.json#/a"}), "$ref: -> other.json#/a\n")

    def test_control_chars_escaped(self):
        out = view({"x": "a\x1b[31mb\tc"})
        self.assertNotIn("\x1b", out)
        self.assertIn("\\x1b[31mb\\x09c", out)

    def test_quotes_only_when_ambiguous(self):
        self.assertEqual(view({"e": "", "l": ["a, b", "c"]}), 'e: ""\nl: ["a, b", c]\n')

    def test_empty_containers_and_scalars(self):
        self.assertEqual(view({"a": [], "b": {}}), "a: []\nb: {}\n")
        self.assertEqual(view(42), "42\n")

    def test_color(self):
        out = view({"k": 1}, color=True)
        self.assertIn("\x1b[1;36mk\x1b[0m", out)
        self.assertIn("\x1b[33m1\x1b[0m", out)


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = os.path.join(self.tmp.name, "a.json")
        with open(self.f, "w") as f:
            json.dump({"a": [{"b/c": "deep", "t~": 1}], "s": "x"}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pointer_in_path_and_second_arg(self):
        r = run(self.f + "#/a/0/b~1c")
        self.assertEqual((r.returncode, r.stdout.splitlines()[1:]), (0, ["deep"]))
        r = run(self.f, "#/a/0/t~0")
        self.assertEqual((r.returncode, r.stdout.splitlines()[1:]), (0, ["1"]))

    def test_pointer_header_line(self):
        r = run(self.f + "#/a")
        self.assertEqual(r.stdout.splitlines()[0], "# %s#/a" % self.f)
        r = run(self.f, "#/a/0")
        self.assertEqual(r.stdout.splitlines()[0], "# %s#/a/0" % self.f)
        self.assertFalse(run(self.f).stdout.startswith("# "))     # no pointer, no header

    def test_depth(self):
        deep = os.path.join(self.tmp.name, "deep.json")
        with open(deep, "w") as f:
            json.dump({"x": {"y": {"p": 1, "q": 2, "r": 3}, "l": [1, 2, 3, 4, 5]}, "e": {}, "t": ["a"]}, f)
        r = run("--depth", "1", deep)
        self.assertEqual(r.stdout, "x: {…2 keys}\ne: {}\nt: [a]\n")
        r = run("--depth", "2", deep)
        self.assertEqual(r.stdout, "x: {y: {…3 keys}, l: […5 items]}\ne: {}\nt: [a]\n")
        r = run("--depth", "0", deep)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, "^aos-json-view: error: ArgumentsBad ")

    def test_no_color_when_piped(self):
        r = run(self.f)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("\x1b", r.stdout)
        self.assertIn("\x1b", run("--color", self.f).stdout)

    def test_file_not_changed(self):
        with open(self.f) as f:
            before = f.read()
        run(self.f)
        with open(self.f) as f:
            self.assertEqual(f.read(), before)

    def test_errors(self):
        cases = [((), "ArgumentsBad"), ((self.f + "#/nope",), "PointerBad"),
                 ((os.path.join(self.tmp.name, "missing.json"),), "FileBad"),
                 (("--width", "x", self.f), "ArgumentsBad"), (("--bogus", self.f), "FlagUnknown")]
        bad = os.path.join(self.tmp.name, "bad.json")
        with open(bad, "w") as f:
            f.write("{nope")
        cases.append(((bad,), "FileBad"))
        for args, code in cases:
            r = run(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertRegex(r.stderr, r"^aos-json-view: error: %s " % code)

    def test_help(self):
        r = run("--help")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith("aos-json-view - "))


if __name__ == "__main__":
    unittest.main()
