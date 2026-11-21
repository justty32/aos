"""Tests for two one-liner fallbacks of the code map (codemap_lib): an empty {} settings file, and a markdown file with no heading."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import codemap_lib  # noqa: E402


class Fallbacks(unittest.TestCase):
    def test_empty_object_settings_file_gets_a_line(self):
        self.assertTrue(codemap_lib.json_desc("{}"))
        self.assertEqual(codemap_lib.json_desc('{"model": "x"}'), "設定（鍵：model）")
        self.assertEqual(codemap_lib.json_desc("[]"), "")

    def test_markdown_without_a_heading_takes_its_first_line(self):
        self.assertEqual(codemap_lib.text_desc("\nOne sentence page.\n\nmore\n", "a/_description.md"), "One sentence page.")
        self.assertEqual(codemap_lib.text_desc("intro\n\n# Title\n", "a/x.md"), "Title")
        self.assertEqual(codemap_lib.text_desc("", "a/x.md"), "")


if __name__ == "__main__":
    unittest.main()
