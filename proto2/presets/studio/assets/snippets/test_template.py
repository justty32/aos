# 這是 snippet，複製後改名成 test_<你的程式>.py，不要直接在這裡改。
"""unittest 樣板：每個測試都用自己的暫存資料檔，測完自動刪，彼此不會互相影響。"""
import contextlib
import importlib
import io
import os
import sys
import tempfile
import unittest

MODULE = "cli_argparse"  # SNIPPET-MODULE：換成你的主程式檔名（不含 .py）

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
app = importlib.import_module(MODULE)


def run(*argv):
    """跑一次 main()，回 (退出碼, 印出來的字)。stdout 與 stderr 都收在一起。"""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = app.main(list(argv))
    return code, out.getvalue()


class CliTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = os.path.join(folder.name, "items.json")

    def test_add_then_list(self):
        code, _ = run("--file", self.data, "add", "買牛奶")
        self.assertEqual(code, 0)
        code, text = run("--file", self.data, "list")
        self.assertEqual(code, 0)
        self.assertIn("買牛奶", text)

    def test_delete(self):
        run("--file", self.data, "add", "買牛奶")
        code, _ = run("--file", self.data, "delete", "1")
        self.assertEqual(code, 0)
        code, text = run("--file", self.data, "list")
        self.assertNotIn("買牛奶", text)

    def test_delete_missing_id(self):
        code, text = run("--file", self.data, "delete", "99")
        self.assertEqual(code, 1)
        self.assertIn("no such id", text)

    def test_list_empty(self):
        code, text = run("--file", self.data, "list")
        self.assertEqual(code, 0)
        self.assertIn("(empty)", text)


if __name__ == "__main__":
    unittest.main()
