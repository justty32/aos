"""Test tool_io.place and tool_io.os_reason: error lines name program-made paths relative to $AOS_STACK / $AOS_DAEMON / $AOS_WS (counted from the caller's stack when AOS_STACK_IN_CALLER says where the cell sits in it), and no OSError file name."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tool_io  # noqa: E402


class Place(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tool-io-place-"))
        self.ws = self.tmp / "project"
        self.daemon = self.ws / "stacks" / "root"
        self.stack = self.daemon / "procs" / "bob" / "tools" / "todo"
        self.stack.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, **kw):
        base = {k: v for k, v in os.environ.items() if k not in ("AOS_STACK", "AOS_DAEMON", "AOS_WS", "AOS_STACK_IN_CALLER")}
        base.update({k: str(v) for k, v in kw.items()})
        return mock.patch.dict(os.environ, base, clear=True)

    def test_nearest_root_wins(self):
        with self.env(AOS_STACK=self.stack, AOS_DAEMON=self.daemon, AOS_WS=self.ws):
            self.assertEqual(tool_io.place(str(self.stack / "todo.json")), "$AOS_STACK/todo.json")
            self.assertEqual(tool_io.place(str(self.stack)), "$AOS_STACK")
            self.assertEqual(tool_io.place(str(self.daemon / "procs" / "kid" / "history.jsonl")), "$AOS_DAEMON/procs/kid/history.jsonl")
            self.assertEqual(tool_io.place(str(self.ws / "notes" / "a.txt")), "notes/a.txt")
            self.assertEqual(tool_io.place("/elsewhere/x"), "/elsewhere/x")       # 都不在＝照原樣

    def test_real_path_of_the_root_also_counts(self):
        link = self.tmp / "link"
        link.symlink_to(self.stack)
        with self.env(AOS_STACK=link):
            self.assertEqual(tool_io.place(str(self.stack / "a.json")), "$AOS_STACK/a.json")
            self.assertEqual(tool_io.place(str(link / "a.json")), "$AOS_STACK/a.json")

    def test_unset_root_is_skipped_a_missing_one_still_counts(self):
        with self.env(AOS_STACK=self.tmp / "gone"):
            self.assertEqual(tool_io.place(str(self.stack / "a.json")), str(self.stack / "a.json"))
            self.assertEqual(tool_io.place(str(self.tmp / "gone" / "a.json")), "$AOS_STACK/a.json")   # 小格還沒建也一樣
        with self.env(AOS_WS=self.ws):
            self.assertEqual(tool_io.shown_path(str(self.ws)), ".")              # shown_path 不變
            self.assertEqual(tool_io.shown_path("/elsewhere"), "/elsewhere")

    def test_in_caller_counts_from_the_callers_stack(self):
        """11-13 fx-2：aos-tools call 給 AOS_STACK_IN_CALLER=tools/<名>，小格裡的路徑印成叫方照自己的 $AOS_STACK 找得到的寫法。"""
        caller = self.stack.parent.parent
        with self.env(AOS_STACK=str(self.stack) + "/", AOS_STACK_IN_CALLER="tools/todo", AOS_DAEMON=self.daemon, AOS_WS=self.ws):
            shown = tool_io.place(str(self.stack / "todo.json"))
            self.assertEqual(shown, "$AOS_STACK/tools/todo/todo.json")
            (self.stack / "todo.json").write_text("{}")
            self.assertTrue(Path(shown.replace("$AOS_STACK", str(caller), 1)).is_file())    # 叫方照字面找得到
            self.assertEqual(tool_io.place(str(self.stack)), "$AOS_STACK/tools/todo")
            self.assertEqual(tool_io.place(str(self.stack / "a" / "b.txt")), "$AOS_STACK/tools/todo/a/b.txt")
            self.assertEqual(tool_io.place(str(caller / "history.jsonl")), "$AOS_DAEMON/procs/bob/history.jsonl")   # 小格外的照舊
            self.assertEqual(tool_io.place(str(self.ws / "notes" / "a.txt")), "notes/a.txt")
        real = self.tmp / "elsewhere"
        real.mkdir()
        link = self.tmp / "caller" / "tools" / "note"
        link.parent.mkdir(parents=True)
        link.symlink_to(real)
        with self.env(AOS_STACK=link, AOS_STACK_IN_CALLER="tools/note"):                    # 小格是捷徑：照字面與真實路徑都算在小格裡
            self.assertEqual(tool_io.place(str(real / "a.json")), "$AOS_STACK/tools/note/a.json")
            self.assertEqual(tool_io.place(str(link / "a.json")), "$AOS_STACK/tools/note/a.json")

    def test_in_caller_that_does_not_fit_is_ignored(self):
        """值跟自己的 AOS_STACK 結尾對不上（被換過 AOS_STACK 的子程式繼承走）、絕對路徑、帶 ..、空＝當沒設，照原本的印法。"""
        for bad in ("tools/other", "ols/todo", "/abs/tools/todo", "tools/../tools/todo", "../todo", "", ".", "tools/todo/x"):
            with self.subTest(bad=bad), self.env(AOS_STACK=self.stack, AOS_STACK_IN_CALLER=bad):
                self.assertEqual(tool_io.place(str(self.stack / "todo.json")), "$AOS_STACK/todo.json")
                self.assertEqual(tool_io.place(str(self.stack)), "$AOS_STACK")
        with self.env(AOS_STACK_IN_CALLER="tools/todo"):                                    # 沒有 AOS_STACK＝沒得對
            self.assertEqual(tool_io.place(str(self.stack / "todo.json")), str(self.stack / "todo.json"))
        with self.env(AOS_STACK=self.stack, AOS_STACK_IN_CALLER="tools/todo/"):             # 結尾多一個 / 照樣認
            self.assertEqual(tool_io.place(str(self.stack / "todo.json")), "$AOS_STACK/tools/todo/todo.json")

    def test_os_reason_drops_the_file_name(self):
        try:
            open(str(self.tmp / "no" / "such"))
        except OSError as e:
            self.assertEqual(tool_io.os_reason(e), "No such file or directory")
            self.assertIn(str(self.tmp), str(e))
        self.assertEqual(tool_io.os_reason(ValueError("bad json")), "bad json")


if __name__ == "__main__":
    unittest.main()
