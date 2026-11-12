"""Test tool_io.place and tool_io.os_reason: error lines name program-made paths relative to $AOS_STACK / $AOS_DAEMON / $AOS_WS, and no OSError file name."""
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
        base = {k: v for k, v in os.environ.items() if k not in ("AOS_STACK", "AOS_DAEMON", "AOS_WS")}
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

    def test_os_reason_drops_the_file_name(self):
        try:
            open(str(self.tmp / "no" / "such"))
        except OSError as e:
            self.assertEqual(tool_io.os_reason(e), "No such file or directory")
            self.assertIn(str(self.tmp), str(e))
        self.assertEqual(tool_io.os_reason(ValueError("bad json")), "bad json")


if __name__ == "__main__":
    unittest.main()
