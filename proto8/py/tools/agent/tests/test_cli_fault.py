# test_cli_fault.py - 驗證 claude API 失敗分類表的優先順序、壞型別容錯與工具計數。
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cli_fault import classify_claude, tool_calls


RETRIES = [json.dumps({"type": "system", "subtype": "api_retry"})]


class Classify(unittest.TestCase):
    def classify(self, **fields):
        return classify_claude(dict(terminal_reason="api_error", **fields), 1, False, [])

    def test_timeout_first(self):
        got = classify_claude(None, -9, True, RETRIES)
        self.assertEqual(got, {"retry": False, "cause": "turn_timeout", "status": None, "tools": 0})

    def test_no_result(self):
        for out in (None, False, 0, "result", [], [1]):
            with self.subTest(out=out):
                self.assertEqual(classify_claude(out, 1, False, RETRIES)["cause"], "no_result")

    def test_budget_and_turn_limits_first(self):
        for subtype in ("error_max_turns", "error_max_budget_usd"):
            with self.subTest(subtype=subtype):
                got = classify_claude({"subtype": subtype, "api_error_status": 529}, 1, False, RETRIES)
                self.assertFalse(got["retry"])
                self.assertEqual(got["cause"], subtype)

    def test_missing_terminal_reason_allows_api_fields(self):
        for fields in ({}, {"terminal_reason": None}, {"terminal_reason": True},
                       {"terminal_reason": []}, {"terminal_reason": {}}):
            with self.subTest(fields=fields):
                got = classify_claude(dict(fields, api_error_status=529), 1, False, [])
                self.assertTrue(got["retry"])
                self.assertEqual(got["cause"], "api_529")

    def test_completed_blocks_api_fields_unless_api_retry(self):
        for terminal in ("completed", "other"):
            for fields in ({"api_error_status": 529}, {"api_error_type": "overloaded_error"},
                           {"api_error": "connection_failed"}):
                with self.subTest(terminal=terminal, fields=fields):
                    out = dict(fields, terminal_reason=terminal)
                    got = classify_claude(out, 1, False, [])
                    self.assertFalse(got["retry"])
                    self.assertEqual(got["cause"], "unknown")
                    got = classify_claude(out, 1, False, RETRIES)
                    self.assertTrue(got["retry"])
                    self.assertEqual(got["cause"], "api_retry_exhausted")

    def test_other_error_subtypes_after_retry(self):
        for subtype in ("error_during_execution", "error_future"):
            with self.subTest(subtype=subtype):
                out = {"subtype": subtype, "terminal_reason": "completed"}
                got = classify_claude(out, 1, False, [])
                self.assertFalse(got["retry"])
                self.assertEqual(got["cause"], subtype)
                got = classify_claude(out, 1, False, RETRIES)
                self.assertTrue(got["retry"])
                self.assertEqual(got["cause"], "api_retry_exhausted")
                self.assertEqual(self.classify(subtype=subtype, api_error_status=529)["cause"], "api_529")

    def test_permanent_statuses(self):
        for status in (400, 401, 403, 404, 413, 422, 499):
            with self.subTest(status=status):
                got = self.classify(api_error_status=status, api_error_type="overloaded_error")
                self.assertEqual(got, {"retry": False, "cause": "api_%d" % status, "status": status, "tools": 0})

    def test_permanent_types(self):
        for kind in ("invalid_request_error", "authentication_error", "permission_error", "not_found_error",
                     "request_too_large", "billing_error"):
            with self.subTest(kind=kind):
                got = self.classify(api_error_type=kind, api_error_status=529)
                self.assertFalse(got["retry"])
                self.assertEqual(got["cause"], kind)

    def test_transient_statuses(self):
        for status in (408, 409, 429, 500, 502, 503, 529, 599):
            with self.subTest(status=status):
                got = self.classify(api_error_status=status, api_error_type="timeout_error")
                self.assertTrue(got["retry"])
                self.assertEqual((got["cause"], got["status"]), ("api_%d" % status, status))

    def test_transient_types(self):
        for kind in ("rate_limit_error", "overloaded_error", "api_error", "timeout_error"):
            with self.subTest(kind=kind):
                got = self.classify(api_error_type=kind, api_error="connection_failed")
                self.assertTrue(got["retry"])
                self.assertEqual(got["cause"], kind)

    def test_connection_failed(self):
        got = self.classify(api_error="connection_failed")
        self.assertTrue(got["retry"])
        self.assertEqual(got["cause"], "connection_failed")

    def test_api_retry_fallback(self):
        got = classify_claude({"terminal_reason": "api_error"}, 1, False, RETRIES)
        self.assertEqual(got, {"retry": True, "cause": "api_retry_exhausted", "status": None, "tools": 0})

    def test_api_retry_then_400_is_permanent(self):
        for terminal in (None, "api_error", "completed"):
            got = classify_claude({"terminal_reason": terminal, "api_error_status": 400}, 1, False, RETRIES)
            self.assertFalse(got["retry"])
            self.assertEqual(got["cause"], "api_400")

    def test_api_retry_does_not_override_permanent_type(self):
        for terminal in (None, "api_error", "completed"):
            got = classify_claude({"terminal_reason": terminal, "api_error_type": "billing_error"}, 1, False, RETRIES)
            self.assertFalse(got["retry"])
            self.assertEqual(got["cause"], "billing_error")

    def test_unknown(self):
        for status in (None, 0, 200, 399, 600):
            got = self.classify(api_error_status=status, api_error_type="unrecognized")
            self.assertFalse(got["retry"])
            self.assertEqual(got["cause"], "unknown")

    def test_bad_field_types_are_absent(self):
        for bad in (None, True, False, "529", 529.0, [], {}):
            with self.subTest(bad=bad):
                got = self.classify(api_error_status=bad, api_error_type=bad, api_error=bad, subtype=bad)
                self.assertEqual(got, {"retry": False, "cause": "unknown", "status": None, "tools": 0})
                got = self.classify(api_error_status=bad, api_error_type="overloaded_error")
                self.assertTrue(got["retry"])
                self.assertIsNone(got["status"])

    def test_exit_code_does_not_guess_cause(self):
        for code in (0, 1, -9, None, "bad"):
            self.assertEqual(classify_claude({}, code, False, [])["cause"], "unknown")


class Tools(unittest.TestCase):
    def test_tool_calls(self):
        assistant = {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "working"}, {"type": "tool_use", "id": "1"},
            None, False, "tool_use", {"type": "tool_use", "id": "2"}]}}
        lines = [json.dumps(assistant), json.dumps({"type": "assistant", "message": {
            "content": [{"type": "tool_use", "id": "3"}]}}),
            json.dumps(dict(assistant, type="user")), "not JSON", "null", "true", "[]", 12,
            '{"type":"assistant","message":null}', '{"type":"assistant","message":{"content":{}}}',
            '{"type":"assistant","message":{"content":"tool_use"}}', b"\xff"]
        self.assertEqual(tool_calls(lines), 3)
        got = classify_claude({"terminal_reason": "api_error", "api_error_status": 529}, 1, False, lines)
        self.assertEqual(got["tools"], 3)
        self.assertEqual(classify_claude(None, 1, False, lines)["tools"], 3)

    def test_bad_lines_container(self):
        for lines in (None, 1, False, {}, "not JSON"):
            self.assertEqual(tool_calls(lines), 0)
            self.assertFalse(classify_claude({}, 1, False, lines)["retry"])

    def test_bad_api_retry_shapes(self):
        lines = ["null", "[]", "bad", '{"type":"assistant","subtype":"api_retry"}',
                 '{"type":"system","subtype":["api_retry"]}']
        self.assertFalse(classify_claude({"terminal_reason": "api_error"}, 1, False, lines)["retry"])


if __name__ == "__main__":
    unittest.main()
