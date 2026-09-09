"""核心是一個函式：aos-run 就是 import 這個模組反覆叫 `run_target()`，拿 `(code, kind)`。"""
import io
import os
import sys
import unittest

from _util import ExecCase

import aos_exec


class TestApi(ExecCase):

    def call(self, *args, **kw):
        """直接在這個進程裡叫 run_target()，回 `(code, kind, 它印的那行 stderr)`。"""
        buf = io.StringIO()
        old, sys.stderr = sys.stderr, buf
        try:
            code, kind = aos_exec.run_target(*args, **kw)
        finally:
            sys.stderr = old
        return code, kind, buf.getvalue()

    def test_run_target_returns_exit_code(self):
        self.inst({"argv": ["sh", "-c", "exit 9"]})
        self.assertEqual(self.call(self.d)[:2], (9, "child"))

    def test_run_target_can_be_called_again_and_again(self):
        """反覆叫就是 aos-run 要做的事；每次都是獨立的一發。"""
        self.inst({"argv": ["sh", "-c", "echo x >> tally.txt"]})
        for _ in range(3):
            self.assertEqual(self.call(self.d)[:2], (0, "child"))
        self.assertEqual(self.read("tally.txt"), "x\nx\nx\n")

    def test_run_target_takes_the_two_options(self):
        self.inst({"argv": ["sleep", "30"]}, "other.json")
        code, kind, _ = self.call(self.d, dir_target="other.json", timeout_ms=200)
        self.assertEqual((code, kind), (143, "child"))       # 逾時也算「跑完了一次」

    def test_run_target_reports_the_reason_on_stderr(self):
        self.inst({"argv": ["true"], "timeout_ms": 5})
        code, kind, err = self.call(self.d)
        self.assertEqual((code, kind), (1, "aos"))
        self.assertTrue(err.startswith("aos-exec: UnknownKey: "), err)

    def test_kind_says_whose_code_it_is(self):
        """三種 kind：child＝子程式跑完了、aos＝aos-exec 自己失敗、usage＝用法錯。"""
        self.assertEqual(self.call(os.path.join(self.d, "沒這個"))[:2], (2, "usage"))
        self.inst("{ 這不是 JSON")
        self.assertEqual(self.call(self.d)[:2], (1, "aos"))
        self.inst({"argv": ["aos-definitely-no-such-program"]})
        self.assertEqual(self.call(self.d)[:2], (127, "child"))     # 找不到程式還是子程式的碼

    def test_cli_turns_aos_failures_into_125(self):
        """命令列才換算：usage→2、aos→125、child→原樣。"""
        self.inst("{ 這不是 JSON")
        self.assertEqual(self.aos(self.d).returncode, 125)
        self.inst({"argv": ["sh", "-c", "exit 1"]})
        self.assertEqual(self.aos(self.d).returncode, 1)     # 子程式自己回 1 就是 1


if __name__ == "__main__":
    unittest.main()
