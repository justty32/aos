# 驗證長跑 watch 可略過 state_path 的行程內快取重新向 kernel 問表檔。
import importlib
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sp = importlib.import_module("daemon_ctl.state_path")


class FreshStatePath(unittest.TestCase):
    def test_fresh_requeries_and_updates_cached_path(self):
        with mock.patch.dict(os.environ, {"AOS_KERNEL": "/kernel"}, clear=True), \
                mock.patch.object(sp, "_asked", {}), \
                mock.patch.object(sp, "_ask_kernel", side_effect=["/first/table.json", "/second/trimmed.json"]) as ask:
            first = sp.state_path()
            self.assertIsInstance(first, sp.TableFile)
            self.assertEqual(sp.state_path(), first)
            self.assertEqual(ask.call_count, 1)
            self.assertEqual(sp.state_path(timeout_s=1, fresh=True), "/second/trimmed.json")
            self.assertEqual(sp.state_path(), "/second/trimmed.json")
            self.assertEqual(ask.call_args_list, [mock.call("/kernel", 3), mock.call("/kernel", 1)])

    def test_failed_fresh_does_not_silently_return_cached_answer(self):
        with mock.patch.dict(os.environ, {"AOS_KERNEL": "/kernel"}, clear=True), \
                mock.patch.object(sp, "_asked", {"/kernel": sp.TableFile("/old.json")}), \
                mock.patch.object(sp, "_ask_kernel", side_effect=sp.Fail("KernelFailed", "no reply")):
            with self.assertRaises(sp.Fail):
                sp.state_path(fresh=True)

    def test_direct_fresh_never_queries_kernel(self):
        with mock.patch.dict(os.environ, {"AOS_KERNEL": "/kernel"}, clear=True), \
                mock.patch("daemon_ctl.table.find_daemon", return_value="/daemon"), \
                mock.patch.object(sp, "_ask_kernel", side_effect=AssertionError("unexpected query")):
            self.assertEqual(sp.state_path("/daemon", fresh=True), "/daemon/procs_state.json")


if __name__ == "__main__":
    unittest.main()
