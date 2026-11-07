"""Verify optional metadata reading, timeout declarations, and safe cost formulas."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import metainfo


class MetainfoTests(unittest.TestCase):
    def assert_error(self, code, function, *args):
        with self.assertRaises(metainfo.MetainfoError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(str(caught.exception))

    def test_read_directory_and_optional_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(metainfo.read(directory))
            path = Path(directory) / "_metainfo.json"
            data = {"cost": {"time_ms": 12}, "custom": [1]}
            path.write_text(json.dumps(data))
            self.assertEqual(metainfo.read(directory), data)
            named_json = Path(directory) / "definition.json"
            named_json.mkdir()
            (named_json / "_metainfo.json").write_text(json.dumps(data))
            self.assertEqual(metainfo.read(named_json), data)

    def test_embedded_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tool.json"
            self.assertIsNone(metainfo.read(path))
            for data, expected in (({}, None), ({"_metainfo": {"timeout_ms": 5}}, {"timeout_ms": 5})):
                path.write_text(json.dumps(data))
                self.assertEqual(metainfo.read(path), expected)
            for data in ([], {"_metainfo": None}, {"_metainfo": 5}):
                path.write_text(json.dumps(data))
                self.assert_error("FileBad", metainfo.read, path)

    def test_bad_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "_metainfo.json"
            for contents in (b"{", b"[]", b"null", b"1", b"\xff"):
                path.write_bytes(contents)
                self.assert_error("FileBad", metainfo.read, directory)
            with patch.object(Path, "read_text", side_effect=PermissionError("Access denied")):
                self.assert_error("FileBad", metainfo.read, directory)

    def test_timeout(self):
        for metadata in (None, {}, {"cost": {"time_ms": 42}}):
            self.assertIsNone(metainfo.timeout_ms(metadata))
        for value, expected in ((0, 0), (1000, 1000), ({"val": 12, "max": 20}, 12), (3.0, 3)):
            self.assertEqual(metainfo.timeout_ms({"timeout_ms": value}), expected)
        for value in (True, "12", None, {}, 1.2, float("inf")):
            self.assert_error("FileBad", metainfo.timeout_ms, {"timeout_ms": value})

    def test_values_and_unknown_evaluators(self):
        self.assertIsNone(metainfo.eval_cost(None, {}))
        for value, expected in ((3, 3.0), (1.5, 1.5), ({"val": 7, "max": 9, "unit": "ms"}, 7.0)):
            result = metainfo.eval_cost(value, {})
            self.assertEqual(result, expected)
            self.assertIsInstance(result, float)
        for evaluator in ("py", "lua", "aos", "future"):
            self.assertIsNone(metainfo.eval_cost({evaluator: "anything"}, {}))
        for value in (True, "3", [], {}, {"val": "3"}, float("nan"), float("inf")):
            self.assert_error("FileBad", metainfo.eval_cost, value, {})

    def test_calculation(self):
        for expression, variables, expected in (
                ("min(4000+in_bytes*1.2, 9e6)", {"in_bytes": 1000}, 5200),
                ("max(-a, (a + 4) / 2) - 1", {"a": 2}, 2),
                ("min(7)", {}, 7),
                ("1 - 2 * 3", {}, -5)):
            self.assertEqual(metainfo.eval_cost({"cal": expression}, variables), expected)

    def test_reject_unsafe_and_unsupported_formulas(self):
        expressions = (
            "__import__('os')", "__secret", "import os", "a.real", "a[0]",
            "sum(1, 2)", "abs(-1)", "2 ** 3", "4 // 2", "4 % 2", "+1",
            "True", "'text'", "[1, 2]", "lambda: 1", "1 if a else 2",
            "min()", "min(a=1)", "max(*a)", "missing + 1", "1 / 0", "1e999",
            "(1 +", "a()", "a.__class__", "1 < 2")
        for expression in expressions:
            with self.subTest(expression=expression):
                self.assert_error("CalBad", metainfo.eval_cost, {"cal": expression}, {"a": 2, "__secret": 3})
        for expression, variables in ((None, {}), ("a", {"a": "1"}), ("a", {"a": True})):
            self.assert_error("CalBad", metainfo.eval_cost, {"cal": expression}, variables)

    def test_errors_do_not_print(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assert_error("CalBad", metainfo.eval_cost, {"cal": "__import__('os')"}, {})
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(errors.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
