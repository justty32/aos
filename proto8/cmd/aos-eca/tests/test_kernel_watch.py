# 驗證 watch 經 kernel 重問表檔、缺欄容錯、空表退出與五秒節流，直連行為不變。
import contextlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / "lib")]
loader = importlib.machinery.SourceFileLoader("kernel_watch_screen", str(PROTO / "cmd/aos-eca/bin/aos-eca-screen"))
spec = importlib.util.spec_from_loader(loader.name, loader)
screen = importlib.util.module_from_spec(spec)
loader.exec_module(screen)
ROWS_AT = screen.dc.rows_at


class KernelWatch(unittest.TestCase):
    def setUp(self):
        self.scope = contextlib.ExitStack()
        self.addCleanup(self.scope.close)
        self.scope.enter_context(mock.patch.dict(os.environ, {"AOS_KERNEL": "/kernel"}, clear=True))
        self.clock = self.scope.enter_context(mock.patch.object(screen.time, "monotonic", return_value=0))
        self.path = self.scope.enter_context(mock.patch.object(screen.dc, "state_path", return_value="/shown/trimmed.json"))
        self.rows = self.scope.enter_context(mock.patch.object(screen.dc, "rows_at", return_value={}))
        self.scope.enter_context(mock.patch.object(screen.dc, "find_daemon", side_effect=AssertionError("unexpected fallback")))
        self.watch = {"name": "original-name"}

    def gone(self, rows, now=0):
        self.rows.return_value = rows
        self.clock.return_value = now
        return screen.gone("/definition", "/stack/ann", self.watch)

    def test_nonstandard_table_path_and_stopped_row(self):
        self.assertEqual(self.gone({"ann": {"stack": "/stack/ann", "phase": "stopped"}}),
                         "watch: original-name is no longer running on the table at /shown/trimmed.json")
        self.path.assert_called_once_with(timeout_s=1, fresh=True)
        self.rows.assert_called_once_with("/shown/trimmed.json")

    def test_running_then_empty_table_exits(self):
        self.assertIsNone(self.gone({"ann": {"stack": "/stack/ann", "phase": "running"}}))
        self.assertIsNotNone(self.gone({}, now=5))

    def test_no_stack_columns_is_unknown(self):
        self.assertIsNone(self.gone({"ann": {"phase": "running"}}))

    def test_missing_phase_waits_until_row_disappears(self):
        self.assertIsNone(self.gone({"ann": {"stack": "/stack/ann"}}))
        self.assertIsNotNone(self.gone({"other": {"stack": "/stack/other", "phase": "running"}}, now=5))

    def test_ten_checks_make_at_most_two_queries(self):
        for now in range(10):
            self.assertIsNone(self.gone({"ann": {"stack": "/stack/ann", "phase": "running"}}, now))
        self.assertEqual(self.path.call_count, 2)
        self.assertEqual(self.rows.call_count, 2)

    def test_query_failures_and_read_failures_are_throttled(self):
        for method in (self.path, self.rows):
            for error in (screen.dc.Fail("KernelFailed", "no reply"), OSError("unreadable"),
                          json.JSONDecodeError("bad table", "{", 1)):
                with self.subTest(method=method, error=error):
                    self.watch = {"name": "ann"}
                    self.path.reset_mock()
                    self.rows.reset_mock()
                    method.side_effect = error
                    for now in range(10):
                        self.assertIsNone(self.gone({}, now))
                    self.assertEqual(self.path.call_count, 2)
                    method.side_effect = None

    def test_real_nonstandard_table_file(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(screen.dc, "rows_at", side_effect=ROWS_AT):
            table = Path(tmp) / "snapshot.json"
            table.write_text(json.dumps({"procs": {"ann": {"stack": "/stack/ann", "phase": "stopped"}}}))
            self.path.return_value = str(table)
            self.assertIn(str(table), screen.gone("/definition", "/stack/ann", self.watch))

    def test_watch_name_is_fixed_at_start(self):
        cell = mock.Mock()
        cell.file.return_value = "/missing/live.jsonl"
        seen = []

        def gone(eca, stack, watch):
            seen.append(dict(watch))
            os.environ["AOS_AGENT"] = "changed"
            return "watch: ann is no longer running on the table at /shown/trimmed.json"

        with mock.patch.object(screen, "cell_of", return_value=(cell, "/stack/ann")), \
                mock.patch.object(screen, "gone", side_effect=gone), mock.patch.object(screen.aos_flags, "warn"):
            screen.cmd_watch("/definition", {})
        self.assertEqual(seen, [{"name": "ann"}])


class DirectWatch(unittest.TestCase):
    def test_direct_remains_unthrottled(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(screen.dc, "find_daemon", return_value="/daemon") as find, \
                mock.patch.object(screen.dc, "rows", return_value={"ann": {"stack": "/stack/ann", "phase": "running"}}), \
                mock.patch.object(screen.dc, "state_path", side_effect=AssertionError("unexpected query")):
            for _ in range(10):
                self.assertIsNone(screen.gone("/definition", "/stack/ann", {}))
            self.assertEqual(find.call_count, 10)


if __name__ == "__main__":
    unittest.main()
