"""Test the shared dotenv parser directly, including expansion and strict failures."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aos.env_file import Error, read_env_file


class EnvFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="env-file-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "secrets.env"

    def read(self, text):
        self.path.write_text(text, encoding="utf-8")
        return read_env_file(self.path)

    def test_assignments_quotes_comments_and_export(self):
        self.assertEqual(self.read(
            "# comment\n\n export A = x # note\nexport\tB=\"${A}y\" # note\n"
            "C='literal # value'\nD=a#b\nE=#fff\nF=\nexport =value\n"),
            {"A": "x", "B": "xy", "C": "literal # value", "D": "a#b", "E": "#fff",
             "F": "", "export": "value"})

    def test_expands_with_current_environment_each_time(self):
        self.path.write_text('TC_KEY="${TC_BASE}/k"\n', encoding="utf-8")
        for base in ("/at-add", "/at-call"):
            with patch.dict(os.environ, {"TC_BASE": base}):
                self.assertEqual(read_env_file(self.path), {"TC_KEY": base + "/k"})

    def test_later_assignments_win_without_changing_environment(self):
        with patch.dict(os.environ, {"A": "inherited"}, clear=True):
            before = dict(os.environ)
            self.assertEqual(self.read("B=${A}\nA=first\nC=${A}\nA=last\nD=${A}\n"),
                             {"A": "last", "B": "inherited", "C": "first", "D": "last"})
            self.assertEqual(dict(os.environ), before)

    def test_expansion_is_not_recursive(self):
        with patch.dict(os.environ, {"BASE": "${UNKNOWN}"}, clear=True):
            self.assertEqual(self.read("A=${BASE}\n"), {"A": "${UNKNOWN}"})

    def test_crlf_and_final_line_without_newline(self):
        self.path.write_bytes(b"A=x\r\nB=${A}y")
        self.assertEqual(read_env_file(self.path), {"A": "x", "B": "xy"})

    def test_strict_failures_include_location_not_secret(self):
        bad_lines = ["not a line", "1A=secret", "A=secret\0", "A= # note", 'A="secret',
                     'A="secret"tail', r'A="sec\ret"', "A='${A}'", "A=${UNKNOWN}",
                     "A=${A", "A=${1A}", "A=${}"]
        with patch.dict(os.environ, {}, clear=True):
            for line in bad_lines:
                with self.subTest(line=line), self.assertRaises(Error) as cm:
                    self.read("# header\n" + line + "\n")
                self.assertEqual(cm.exception.code, "DotenvBad")
                self.assertEqual(cm.exception.line, 2)
                self.assertEqual(str(cm.exception), "bad env file %s at line 2" % self.path)
                self.assertNotIn("secret", str(cm.exception).replace(str(self.path), ""))

    def test_invalid_utf8(self):
        self.path.write_bytes(b"A=x\nB=\xff\n")
        with self.assertRaises(Error) as cm:
            read_env_file(self.path)
        self.assertEqual(str(cm.exception), "bad env file %s at line 2" % self.path)
        self.assertIsInstance(cm.exception.cause, UnicodeDecodeError)

    def test_missing_file(self):
        with self.assertRaises(Error) as cm:
            read_env_file(self.path)
        self.assertEqual(str(cm.exception), "cannot read env file %s" % self.path)
        self.assertIsInstance(cm.exception.cause, FileNotFoundError)


if __name__ == "__main__":
    unittest.main()
