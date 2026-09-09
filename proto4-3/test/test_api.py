"""核心是一個函式：之後的 aos-run 會 import 這個模組反覆叫 run_target()。"""
import io
import os
import sys
import unittest

from _util import ExecCase

import aos_exec


class TestApi(ExecCase):

    def call(self, *args, **kw):
        """直接在這個進程裡叫 run_target()，順便把它印的那行 stderr 收下來。"""
        buf = io.StringIO()
        old, sys.stderr = sys.stderr, buf
        try:
            return aos_exec.run_target(*args, **kw), buf.getvalue()
        finally:
            sys.stderr = old

    def test_run_target_returns_exit_code(self):
        self.inst({"argv": ["sh", "-c", "exit 9"]})
        self.assertEqual(self.call(self.d)[0], 9)

    def test_run_target_can_be_called_again_and_again(self):
        """反覆叫就是 aos-run 要做的事；每次都是獨立的一發。"""
        self.inst({"argv": ["sh", "-c", "echo x >> tally.txt"]})
        for _ in range(3):
            self.assertEqual(self.call(self.d)[0], 0)
        self.assertEqual(self.read("tally.txt"), "x\nx\nx\n")

    def test_run_target_takes_the_two_options(self):
        self.inst({"argv": ["sleep", "30"]}, "other.json")
        code, _ = self.call(self.d, dir_target="other.json", timeout_ms=200)
        self.assertEqual(code, 143)

    def test_run_target_reports_the_reason_on_stderr(self):
        self.inst({"argv": ["true"], "timeout_ms": 5})
        code, err = self.call(self.d)
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("aos-exec: UnknownKey: "), err)


if __name__ == "__main__":
    unittest.main()
