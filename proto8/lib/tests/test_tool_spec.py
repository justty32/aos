"""Test lib/tool_spec.py: declaration to _tooldef/_metainfo, SpecBad, write_defs into a folder and a JSON pointer, and main() at run time."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import tool_spec as ts  # noqa: E402

SCRIPT = '''\
import sys
sys.path.insert(0, %r)
import tool_spec as ts
P = [ts.param("word", "string", "a word"),
     ts.param("times", "integer", "how many", default=2),
     ts.param("mode", "string", "how", enum=["up", "low"], default="up")]
def run(args):
    if args["word"] == "x":
        ts.fail("WordBad", "x is not a word")
    if args["word"] == "boom":
        return 1 / 0
    if args["word"] == "obj":
        return {"n": args["times"]}
    w = args["word"].upper() if args["mode"] == "up" else args["word"]
    return " ".join([w] * args["times"])
ts.main(run, "Repeat a word. Example: {\\"word\\": \\"hi\\"} -> HI HI", P, {"deterministic": True})
''' % str(LIB)


class Declaration(unittest.TestCase):
    def test_tooldef_shape(self):
        td = ts.tooldef("Do it. More.", [ts.param("a", "number", "first"), ts.param("n", "integer", "count", default=1),
                                         ts.param("w", "array", "words", items="string")], ["CityMissing"])
        self.assertEqual(td["parameters"]["required"], ["a", "w"])
        self.assertEqual(td["parameters"]["properties"]["n"], {"type": "integer", "description": "count", "default": 1})
        self.assertEqual(td["parameters"]["properties"]["w"]["items"], {"type": "string"})
        self.assertEqual(td["errors"], ["ArgumentsBad", "CityMissing", "RunFailed"])
        self.assertEqual(ts.tooldef_problems(td), [])

    def test_metainfo_defaults_and_override(self):
        mi = ts.metainfo("Send a letter. It goes out.", {"side_effect": True, "price": 3})
        self.assertEqual(mi["summary"], "Send a letter")
        self.assertTrue(mi["side_effect"])
        self.assertEqual(mi["price"], 3)               # 不認得的 key 照收
        self.assertEqual(ts.metainfo_problems(mi), [])

    def test_spec_bad(self):
        cases = [lambda: ts.tooldef("", []),
                 lambda: ts.tooldef("d", [ts.param("a", "num", "x")]),
                 lambda: ts.tooldef("d", [ts.param("A", "string", "x")]),
                 lambda: ts.tooldef("d", [ts.param("a", "string", "")]),
                 lambda: ts.tooldef("d", [ts.param("a", "integer", "x", default="1")]),
                 lambda: ts.tooldef("d", [ts.param("a", "string", "x", enum=["p"], default="q")]),
                 lambda: ts.tooldef("d", [ts.param("a", "string", "x"), ts.param("a", "string", "y")]),
                 lambda: ts.tooldef("d", [], ["not a code"]),
                 lambda: ts.metainfo("d", {"timeout_ms": -1}),
                 lambda: ts.metainfo("d", {"side_effect": "no"})]
        for i, f in enumerate(cases):
            with self.subTest(i=i):
                self.assertRaises(ts.SpecBad, f)

    def test_zero_timeout_is_valid_and_negative_is_refused(self):
        self.assertEqual(ts.metainfo("d", {"timeout_ms": 0})["timeout_ms"], 0)
        self.assertEqual(ts.metainfo_problems({"timeout_ms": 0}), [])
        for value in (-1, 1.5, True):
            with self.subTest(value=value):
                self.assertEqual(ts.metainfo_problems({"timeout_ms": value}), [
                    "timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit; the tool is killed after it)"])

    def test_problems_catch_handwritten_mistakes(self):
        self.assertTrue(ts.tooldef_problems({"description": "d", "parameters": {"type": "object", "properties": {"a": {"type": "num"}}}}))
        self.assertTrue(ts.tooldef_problems({"parameters": {}}))
        self.assertTrue(ts.metainfo_problems({"timeout_ms": "10"}))


class Runtime(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tool-spec-")
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name) / "rep"
        self.dir.mkdir()
        (self.dir / "tool.py").write_text(SCRIPT)

    def call(self, *argv, stdin="{}"):
        return subprocess.run([sys.executable, str(self.dir / "tool.py"), *argv], input=stdin, text=True,
                              capture_output=True, timeout=30, env=dict(os.environ, AOS_WS=self.temp.name))

    def test_run_defaults_enum_and_errors(self):
        self.assertEqual(self.call(stdin='{"word": "hi"}').stdout, "HI HI\n")
        self.assertEqual(self.call(stdin='{"word": "hi", "times": 1, "mode": "low"}').stdout, "hi\n")
        self.assertEqual(self.call(stdin='{"word": "obj"}').stdout, '{"n": 2}\n')
        for stdin, code in (('{}', "ArgumentsBad missing word"), ('{"word": "a", "zz": 1}', "ArgumentsBad unknown key zz"),
                            ('{"word": "a", "mode": "mid"}', "ArgumentsBad mode must be one of: up, low"),
                            ('{"word": "x"}', "WordBad x is not a word"),
                            ('{"word": "boom"}', "RunFailed run() raised ZeroDivisionError: division by zero (tool.py line 11)")):
            with self.subTest(stdin=stdin):
                r = self.call(stdin=stdin)
                self.assertEqual(r.returncode, 1)
                self.assertTrue(r.stdout.startswith("rep: error: " + code), r.stdout)
                self.assertEqual(r.stdout, r.stderr)

    def test_zero_timeout_metadata_does_not_prevent_delayed_run(self):
        script = SCRIPT.replace('def run(args):', 'def run(args):\n    __import__("time").sleep(1)')
        script = script.replace('{"deterministic": True}', '{"deterministic": True, "timeout_ms": 0}')
        (self.dir / "tool.py").write_text(script)
        r = self.call(stdin='{"word": "hi"}')
        self.assertEqual((r.returncode, r.stdout), (0, "HI HI\n"), r.stderr)
        self.assertEqual(json.loads(self.call("--metainfo").stdout)["timeout_ms"], 0)

    def test_tooldef_flag_lists_fail_codes_and_help(self):
        td = json.loads(self.call("--tooldef").stdout)
        self.assertEqual(td["errors"], ["ArgumentsBad", "WordBad", "RunFailed"])
        self.assertIn("--times N", self.call("--help").stdout)
        self.assertEqual(json.loads(self.call("--metainfo").stdout)["summary"], "Repeat a word")

    def test_write_defs_folder_and_pointer(self):
        r = self.call("--write-defs")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.dir / "_tooldef.json").read_text()), json.loads(self.call("--tooldef").stdout))
        self.assertTrue((self.dir / "_metainfo.json").is_file())
        box = Path(self.temp.name) / "box.json"
        box.write_text('{"tools": {"rep": {"_entry": ["python3", "rep/tool.py"]}}}')
        r = self.call("--write-defs", "%s#/tools/rep" % box)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(box.read_text())["tools"]["rep"]
        self.assertEqual(got["_entry"], ["python3", "rep/tool.py"])
        self.assertEqual(got["_tooldef"]["errors"][1], "WordBad")
        self.assertEqual(got["_metainfo"]["summary"], "Repeat a word")

    def test_bad_declaration_is_an_error_line(self):
        (self.dir / "tool.py").write_text(SCRIPT.replace('"integer", "how many"', '"int", "how many"'))
        r = self.call(stdin='{"word": "a"}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("rep: error: SpecBad param times: type 'int' must be one of", r.stdout)


if __name__ == "__main__":
    unittest.main()
