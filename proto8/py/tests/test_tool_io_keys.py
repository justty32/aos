"""不認得的 stdin 鍵＝ArgumentsBad（使用者 11-10 晚「那就報錯」）；additionalProperties 與自由物件照舊收。"""

import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tool_io

SCHEMA = {"type": "object", "properties": {
    "op": {"type": "string"},
    "free": {"type": "object"},
    "env": {"type": "object", "additionalProperties": {"type": "string"}},
    "check": {"type": "object", "properties": {"min": {"type": "integer"}}},
    "items": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}}}},
}}


def run(stdin, schema=SCHEMA):
    tool_io.start("t", tooldef={"description": "test", "parameters": schema})
    out, err = io.StringIO(), io.StringIO()
    with patch.object(sys, "argv", ["t"]), patch.object(sys, "stdin", io.StringIO(json.dumps(stdin))), \
         patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
        try:
            return tool_io.arguments(), ""
        except SystemExit:
            return None, err.getvalue()


class UnknownKeyTests(unittest.TestCase):
    def test_top_level_unknown_key(self):
        a, err = run({"op": "x", "bogus": 1})
        self.assertIsNone(a)
        self.assertIn("t: error: ArgumentsBad unknown key bogus (known: op, free, env, check, items)", err)

    def test_nested_declared_object_and_array_items(self):
        self.assertIn("unknown key max in check", run({"check": {"min": 1, "max": 2}})[1])
        self.assertIn("unknown key path in items[0]", run({"items": [{"name": "a", "path": "b"}]})[1])

    def test_top_level_description_is_a_file_header(self):
        a, _ = run({"description": "A case input.", "op": "x"})
        self.assertEqual(a["op"], "x")
        self.assertIn("unknown key description in check", run({"check": {"description": "no"}})[1])

    def test_free_objects_take_any_key(self):
        a, _ = run({"free": {"anything": 1}, "env": {"K": "v"}})
        self.assertEqual(a["free"], {"anything": 1})

    def test_no_parameters_takes_nothing(self):
        self.assertIn("unknown key x (known: none)", run({"x": 1}, {"type": "object", "properties": {}})[1])

    def test_additional_properties_true_opts_out(self):
        a, _ = run({"x": 1}, {"type": "object", "properties": {"op": {"type": "string"}}, "additionalProperties": True})
        self.assertEqual(a, {"x": 1})

    def test_help_says_unknown_key_is_an_error(self):
        text = tool_io.help_from_tooldef("t", {"description": "test", "parameters": SCHEMA})
        self.assertIn("A key the tool does not know is ArgumentsBad", text)
        self.assertNotIn("ignored", text)
        open_td = {"description": "test", "parameters": {"type": "object", "additionalProperties": True, "properties": {"a": {"type": "string"}}}}
        self.assertIn("Keys the tool does not know are passed through", tool_io.help_from_tooldef("t", open_td))


if __name__ == "__main__":
    unittest.main()
