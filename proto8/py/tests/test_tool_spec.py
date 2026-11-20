"""Test py/aos/tool_spec.py (the internal parts behind fn and tools_def): param, tooldef, metainfo, SpecBad, the problem lists; fn.main is in test_fn_run.py."""
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from aos import tool_spec  # noqa: E402


class Declaration(unittest.TestCase):
    def test_tooldef_shape(self):
        td = tool_spec.tooldef("Do it. More.", [tool_spec.param("a", "number", "first"), tool_spec.param("n", "integer", "count", default=1),
                                                tool_spec.param("w", "array", "words", items="string")], ["CityMissing"])
        self.assertEqual(td["parameters"]["required"], ["a", "w"])
        self.assertEqual(td["parameters"]["properties"]["n"], {"type": "integer", "description": "count", "default": 1})
        self.assertEqual(td["parameters"]["properties"]["w"]["items"], {"type": "string"})
        self.assertEqual(td["errors"], ["ArgumentsBad", "CityMissing", "RunFailed"])
        self.assertEqual(tool_spec.tooldef_problems(td), [])

    def test_metainfo_defaults_and_override(self):
        mi = tool_spec.metainfo("Send a letter. It goes out.", {"side_effect": True, "price": 3})
        self.assertEqual(mi["summary"], "Send a letter")
        self.assertTrue(mi["side_effect"])
        self.assertEqual(mi["price"], 3)               # 不認得的 key 照收
        self.assertEqual(tool_spec.metainfo_problems(mi), [])

    def test_spec_bad(self):
        cases = [lambda: tool_spec.tooldef("", []),
                 lambda: tool_spec.tooldef("d", [tool_spec.param("a", "num", "x")]),
                 lambda: tool_spec.tooldef("d", [tool_spec.param("A", "string", "x")]),
                 lambda: tool_spec.tooldef("d", [tool_spec.param("a", "string", "")]),
                 lambda: tool_spec.tooldef("d", [tool_spec.param("a", "integer", "x", default="1")]),
                 lambda: tool_spec.tooldef("d", [tool_spec.param("a", "string", "x", enum=["p"], default="q")]),
                 lambda: tool_spec.tooldef("d", [tool_spec.param("a", "string", "x"), tool_spec.param("a", "string", "y")]),
                 lambda: tool_spec.tooldef("d", [], ["not a code"]),
                 lambda: tool_spec.metainfo("d", {"timeout_ms": -1}),
                 lambda: tool_spec.metainfo("d", {"side_effect": "no"})]
        for i, f in enumerate(cases):
            with self.subTest(i=i):
                self.assertRaises(tool_spec.SpecBad, f)

    def test_zero_timeout_is_valid_and_negative_is_refused(self):
        self.assertEqual(tool_spec.metainfo("d", {"timeout_ms": 0})["timeout_ms"], 0)
        self.assertEqual(tool_spec.metainfo_problems({"timeout_ms": 0}), [])
        for value in (-1, 1.5, True):
            with self.subTest(value=value):
                self.assertEqual(tool_spec.metainfo_problems({"timeout_ms": value}), [
                    "timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit; the tool is killed after it)"])

    def test_problems_catch_handwritten_mistakes(self):
        self.assertTrue(tool_spec.tooldef_problems({"description": "d", "parameters": {"type": "object", "properties": {"a": {"type": "num"}}}}))
        self.assertTrue(tool_spec.tooldef_problems({"parameters": {}}))
        self.assertTrue(tool_spec.metainfo_problems({"timeout_ms": "10"}))


if __name__ == "__main__":
    unittest.main()
