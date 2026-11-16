# test_retry_file.py - 驗證 retry.json 的讀寫清除、累加去重、壞檔容錯與續做提示。
import datetime
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("retry_file", HERE.parent / "aos_eca" / "retry.py")
retry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retry)


class RetryFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="eca-retry-file-")
        self.addCleanup(self.tmp.cleanup)
        self.stack = Path(self.tmp.name)
        self.file = self.stack / "retry.json"

    def note(self, letters=(), tools=0, cause="api_529", code="CliFailed", reason="claude exited 1: API Error"):
        return retry.note(self.stack, letters, code, reason, {"tools": tools, "cause": cause})

    def test_path_missing_read_and_clear(self):
        self.assertEqual(retry.path(self.stack), str(self.file))
        self.assertIsNone(retry.read(self.stack))
        retry.clear(self.stack)

    def test_note_read_clear(self):
        rec = self.note(["letter-a", "letter-b"], tools=3)
        self.assertEqual(rec, retry.read(self.stack))
        self.assertEqual(rec["letters"], ["letter-a", "letter-b"])
        self.assertEqual((rec["attempt"], rec["tools"], rec["cause"]), (1, 3, "api_529"))
        self.assertEqual(rec["code"], "CliFailed")
        self.assertEqual(rec["reason"], "claude exited 1: API Error")
        datetime.datetime.strptime(rec["at"], "%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(set(rec), {"letters", "attempt", "code", "cause", "reason", "tools", "at"})
        retry.clear(self.stack)
        self.assertFalse(self.file.exists())
        self.assertIsNone(retry.read(self.stack))
        retry.clear(self.stack)

    def test_dedupe_attempt_and_tools(self):
        self.note(["a", "a", "b"], tools=2)
        rec = self.note(["b", "c", "c", "a"], tools=3, cause="connection_failed", reason="connection refused")
        self.assertEqual(rec["letters"], ["a", "b", "c"])
        self.assertEqual((rec["attempt"], rec["tools"]), (2, 5))
        self.assertEqual((rec["cause"], rec["reason"]), ("connection_failed", "connection refused"))
        rec = self.note([], tools=0)
        self.assertEqual((rec["attempt"], rec["tools"], rec["letters"]), (3, 5, ["a", "b", "c"]))
        self.assertEqual(retry.read(self.stack), rec)

    def test_goal_without_letters(self):
        rec = self.note()
        self.assertEqual(rec["letters"], [])
        self.assertEqual((rec["attempt"], rec["tools"]), (1, 0))
        self.assertEqual(retry.read(self.stack), rec)

    def test_bad_file(self):
        for text in ("{", "null", "[]", "true", "42", '"text"', "{}"):
            with self.subTest(text=text):
                self.file.write_text(text, encoding="utf-8")
                self.assertIsNone(retry.read(self.stack))
        self.file.write_bytes(b"\xff")
        self.assertIsNone(retry.read(self.stack))
        rec = self.note(["new"], tools=1)
        self.assertEqual((rec["attempt"], rec["tools"], rec["letters"]), (1, 1, ["new"]))

    def test_bad_fields(self):
        good = self.note(["a"])
        bad_values = {"letters": (None, "a", {}, [1], [False]),
                      "attempt": (None, True, 0, -1, "2", 1.5),
                      "tools": (None, False, -1, "2", 1.5),
                      "code": (None, 12, [], {}), "cause": (None, False, []),
                      "reason": (None, 12, []), "at": (None, 12, "bad", "2026-99-99T00:00:00Z")}
        for key, values in bad_values.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.file.write_text(json.dumps(dict(good, **{key: value})), encoding="utf-8")
                    self.assertIsNone(retry.read(self.stack))
            without = dict(good)
            del without[key]
            self.file.write_text(json.dumps(without), encoding="utf-8")
            self.assertIsNone(retry.read(self.stack))

    def test_bad_info_is_not_persisted(self):
        for info in (None, [], {"tools": True}, {"tools": -1}, {"tools": "3", "cause": []}):
            with self.subTest(info=info):
                retry.clear(self.stack)
                rec = retry.note(self.stack, [], "CliFailed", "failed", info)
                self.assertEqual((rec["tools"], rec["cause"]), (0, "unknown"))
                self.assertEqual(retry.read(self.stack), rec)

    def test_atomic_replace(self):
        old = self.note(["a"])
        replace = os.replace
        calls = []

        def inspect(source, dest):
            calls.append((source, dest))
            self.assertTrue(str(source).endswith(".tmp"))
            self.assertEqual(Path(source).parent, self.stack)
            self.assertEqual(retry.read(self.stack), old)
            self.assertEqual(json.loads(Path(source).read_text())["attempt"], 2)
            replace(source, dest)

        with mock.patch.object(retry.os, "replace", side_effect=inspect):
            new = self.note(["b"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(retry.read(self.stack), new)
        self.assertFalse(Path(calls[0][0]).exists())

    def test_write_error_propagates(self):
        with self.assertRaises(OSError):
            retry.note(self.stack / "missing", ["a"], "CliFailed", "failed", {})
        old = self.note(["a"])
        with mock.patch.object(retry.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                self.note(["b"])
        self.assertEqual(retry.read(self.stack), old)

    def test_clear_error_propagates(self):
        with mock.patch.object(retry.os, "remove", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                retry.clear(self.stack)

    def test_prompt_without_tools(self):
        rec = self.note(["a", "b"])
        self.assertEqual(retry.prompt(rec),
                         "[aos] retry: the last turn failed before you answered (CliFailed: claude exited 1: API Error). "
                         "Its messages (2 letters) are already in this conversation, or in the record above. "
                         "Go on from where it stopped and answer them now.")
        self.assertNotIn("already called tools", retry.prompt(rec))

    def test_prompt_without_letters(self):
        rec = self.note([])
        expected = ("[aos] retry: the last turn failed before you answered (CliFailed: claude exited 1: API Error). "
                    "Its prompt is already in this conversation, or in the record above. "
                    "Go on from where it stopped and answer it now.")
        self.assertEqual(retry.prompt(rec), expected)
        self.assertNotIn("0 letters", retry.prompt(rec))
        rec["tools"] = 2
        self.assertEqual(retry.prompt(rec), expected +
                         " You had already called tools in that turn (2 calls): "
                         "check what is already done before doing anything again.")

    def test_prompt_with_tools(self):
        rec = self.note(["a"], tools=3)
        self.assertTrue(retry.prompt(rec).endswith(
            "You had already called tools in that turn (3 calls): "
            "check what is already done before doing anything again."))
        self.assertIn("Its messages (1 letters)", retry.prompt(rec))


if __name__ == "__main__":
    unittest.main()
