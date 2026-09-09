"""退出碼：原樣傳回、127／126、開檔失敗、exit 檔的父目錄不見，還有 --timeout-ms。"""
import os
import sys
import time
import unittest

from _util import ExecCase

# 一個攔下 SIGTERM 不理的程式：只有 SIGKILL 弄得死它。
IGNORE_TERM = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); " \
              "time.sleep(30)"


class TestStatus(ExecCase):

    def test_exit_code_passthrough(self):
        self.inst({"argv": ["sh", "-c", "exit 42"]})
        self.assertEqual(self.aos(self.d).returncode, 42)

    def test_signalled_is_128_plus_n(self):
        self.inst({"argv": ["sh", "-c", "kill -TERM $$"]})
        self.assertEqual(self.aos(self.d).returncode, 143)

    def test_command_not_found_is_127(self):
        self.inst({"argv": ["aos-definitely-no-such-program"]})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 127)
        self.assertIn("找不到程式", r.stderr)

    def test_not_executable_is_126(self):
        self.write("noexec.sh", "#!/bin/sh\necho hi\n")
        self.inst({"argv": ["./noexec.sh"]})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 126)
        self.assertIn("沒有執行權", r.stderr)

    def test_stdout_open_failure_is_126(self):
        self.inst({"argv": ["true"], "stdout": "沒有這個資料夾/out.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 126)
        self.assertIn("重導向的檔案開不起來", r.stderr)

    def test_stdin_open_failure_is_126(self):
        self.inst({"argv": ["true"], "stdin": "沒有這個檔.txt"})
        self.assertEqual(self.aos(self.d).returncode, 126)

    def test_stderr_open_failure_is_126(self):
        self.inst({"argv": ["true"], "stderr": "沒有這個資料夾/err.txt"})
        self.assertEqual(self.aos(self.d).returncode, 126)

    def test_exit_parent_dir_missing_is_1(self):
        """exit 檔的父目錄不存在＝aos-exec 自己失敗，不 mkdir、也不跑那個指令。"""
        self.inst({"argv": ["sh", "-c", "echo 跑到了 > 證據.txt"],
                   "exit": "沒有這個資料夾/code.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("父目錄不存在", r.stderr)
        self.assertFalse(self.exists("證據.txt"))

    def test_cwd_missing_is_126(self):
        self.inst({"argv": ["true"], "cwd": "沒有這個資料夾"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 126)
        self.assertIn("cwd", r.stderr)

    def test_timeout_sigterm_is_143(self):
        self.inst({"argv": ["sleep", "30"]})
        t0 = time.monotonic()
        r = self.aos(self.d, "--timeout-ms", "200")
        self.assertEqual(r.returncode, 143)
        self.assertLess(time.monotonic() - t0, 5)      # SIGTERM 就死，不用等寬限期

    def test_timeout_sigkill_is_137(self):
        """攔下 SIGTERM 不理的：給 2 秒寬限期，還活著就 SIGKILL＝137。"""
        self.inst({"argv": [sys.executable, "-c", IGNORE_TERM]})
        t0 = time.monotonic()
        r = self.aos(self.d, "--timeout-ms", "200")
        self.assertEqual(r.returncode, 137)
        self.assertGreater(time.monotonic() - t0, 1.5)

    def test_timeout_writes_exit_file(self):
        self.inst({"argv": ["sleep", "30"], "exit": "code.txt"})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "200").returncode, 143)
        self.assertEqual(self.read("code.txt"), "143\n")

    def test_timeout_kills_the_whole_group(self):
        """砍的是整個 process group，孫行程要跟著走。"""
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "sleep 30 & echo $! > pid.txt; wait"],
                   "exit": "code.txt"})
        self.assertIn(self.aos(self.d, "--timeout-ms", "300").returncode, (137, 143))
        pid = int(self.read("pid.txt").strip())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and os.path.exists("/proc/%d" % pid):
            time.sleep(0.05)
        self.assertFalse(os.path.exists("/proc/%d" % pid))

    def test_timeout_zero_means_no_limit(self):
        self.inst({"argv": ["sh", "-c", "sleep 0.3; exit 5"]})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "0").returncode, 5)

    def test_timeout_applies_to_plain_file_mode(self):
        p = self.write("slow.sh", "#!/bin/sh\nsleep 30\n", executable=True)
        self.assertEqual(self.aos(p, "--timeout-ms", "200").returncode, 143)

    def test_timeout_applies_to_json_mode(self):
        self.inst({"argv": ["sleep", "30"]}, "one.json")
        self.assertEqual(
            self.aos(os.path.join(self.d, "one.json"), "--timeout-ms", "200").returncode,
            143)

    def test_not_timed_out_returns_normally(self):
        self.inst({"argv": ["sh", "-c", "exit 3"]})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "10000").returncode, 3)


if __name__ == "__main__":
    unittest.main()
