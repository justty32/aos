"""aos_exec：真的跑——三種目標、退出碼、選項落地（append／mkdir／inherit／merge／clear）、逾時、

本檔：退出碼、API、逾時（TestStatus、TestApi、TestRunInstTimeout）。

run_target() 的 API。案例從 proto4-3 的 test_targets／test_status／test_opts／test_env／test_api 搬來。

大多數條目透過 cli/aos-exec 開子進程（驗命令列的退出碼與 stderr），API 那群直接 import。
"""
import io
import os
import subprocess
import sys
import time
import unittest

from _util import ExecCase

import aos_exec
import aos_inst


# 一個攔下 SIGTERM 不理的程式：只有 SIGKILL 弄得死它。
IGNORE_TERM = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"


# ---------------------------------------------------------------- 退出碼與逾時 ----
class TestStatus(ExecCase):

    def test_exit_code_passthrough(self):
        self.inst({"argv": ["sh", "-c", "exit 42"]})
        self.assertEqual(self.aos(self.d).returncode, 42)
        self.inst({"argv": ["sh", "-c", "exit 1"]})
        self.assertEqual(self.aos(self.d).returncode, 1)     # 子程式自己回 1 就是 1，不會跟 125 混

    def test_signalled_is_128_plus_n(self):
        self.inst({"argv": ["sh", "-c", "kill -TERM $$"]})
        self.assertEqual(self.aos(self.d).returncode, 143)

    def test_command_not_found_is_127_and_writes_exit(self):
        self.inst({"argv": ["aos-definitely-no-such-program"], "exit": "code.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 127)
        self.assertIn("找不到程式", r.stderr)
        self.assertEqual(self.read("code.txt"), "127\n")

    def test_not_executable_is_126_and_writes_exit(self):
        self.write("noexec.sh", "#!/bin/sh\necho hi\n")
        self.inst({"argv": ["./noexec.sh"], "exit": "code.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 126)
        self.assertIn("沒有執行權", r.stderr)
        self.assertEqual(self.read("code.txt"), "126\n")

    def test_timeout_sigterm_is_143(self):
        self.inst({"argv": ["sleep", "30"]})
        t0 = time.monotonic()
        r = self.aos(self.d, "--timeout-ms", "200")
        self.assertEqual(r.returncode, 143)
        self.assertLess(time.monotonic() - t0, 5)      # SIGTERM 就死，不用等寬限期

    def test_timeout_sigkill_is_137(self):
        """攔下 SIGTERM 不理的：給 2 秒寬限期，還活著就 SIGKILL＝137。"""
        self.inst({"argv": [sys.executable, "-c", IGNORE_TERM], "exit": "code.txt"})
        t0 = time.monotonic()
        r = self.aos(self.d, "--timeout-ms", "200")
        self.assertEqual(r.returncode, 137)
        self.assertGreater(time.monotonic() - t0, 1.5)
        self.assertEqual(self.read("code.txt"), "137\n")

    def test_timeout_writes_exit_file(self):
        self.inst({"argv": ["sleep", "30"], "exit": "code.txt"})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "200").returncode, 143)
        self.assertEqual(self.read("code.txt"), "143\n")

    def test_timeout_kills_the_whole_group(self):
        """砍的是整個 process group，孫行程要跟著走。"""
        self.inst({"argv": ["sh", "-c", "sleep 30 & echo $! > pid.txt; wait"]})
        self.assertIn(self.aos(self.d, "--timeout-ms", "300").returncode, (137, 143))
        pid = int(self.read("pid.txt").strip())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and os.path.exists("/proc/%d" % pid):
            time.sleep(0.05)
        self.assertFalse(os.path.exists("/proc/%d" % pid))

    def test_timeout_zero_means_no_limit(self):
        self.inst({"argv": ["sh", "-c", "sleep 0.3; exit 5"]})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "0").returncode, 5)

    def test_timeout_applies_to_plain_file_and_json_mode(self):
        p = self.write("slow.sh", "#!/bin/sh\nsleep 30\n", executable=True)
        self.assertEqual(self.aos(p, "--timeout-ms", "200").returncode, 143)
        self.inst({"argv": ["sleep", "30"]}, "one.json")
        self.assertEqual(self.aos(os.path.join(self.d, "one.json"), "--timeout-ms", "200").returncode, 143)

    def test_not_timed_out_returns_normally(self):
        self.inst({"argv": ["sh", "-c", "exit 3"]})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "10000").returncode, 3)


# ---------------------------------------------------------------- API ----

class TestApi(ExecCase):
    """核心是一個函式：aos-run 就是 import 這個模組反覆叫 run_target()，拿 (code, kind)。"""

    def call(self, *args, **kw):
        buf = io.StringIO()
        old, sys.stderr = sys.stderr, buf
        try:
            code, kind = aos_exec.run_target(*args, **kw)
        finally:
            sys.stderr = old
        return code, kind, buf.getvalue()

    def test_returns_exit_code(self):
        self.inst({"argv": ["sh", "-c", "exit 9"]})
        self.assertEqual(self.call(self.d)[:2], (9, "child"))

    def test_can_be_called_again_and_again(self):
        self.inst({"argv": ["sh", "-c", "echo x >> tally.txt"]})
        for _ in range(3):
            self.assertEqual(self.call(self.d)[:2], (0, "child"))
        self.assertEqual(self.read("tally.txt"), "x\nx\nx\n")

    def test_takes_timeout(self):
        """proto6 改：拿掉 dir_target 參數；資料夾只有 inst.json 也照找。"""
        self.inst({"argv": ["sleep", "30"]}, "inst.json")
        self.assertEqual(self.call(self.d, timeout_ms=200)[:2], (143, "child"))

    def test_reports_the_reason_on_stderr(self):
        self.inst({"argv": "true"})
        code, kind, err = self.call(self.d)
        self.assertEqual((code, kind), (1, "aos"))
        self.assertTrue(err.startswith("aos-exec: FieldTypeMismatch: "), err)

    def test_kind_says_whose_code_it_is(self):
        self.assertEqual(self.call(os.path.join(self.d, "沒這個"))[:2], (1, "usage"))   # proto6 改：用法錯 1
        self.assertEqual(self.call(self.d, args=[])[:2], (1, "usage"))     # 資料夾目標給了 --
        self.inst("{ 這不是 JSON")
        self.assertEqual(self.call(self.d)[:2], (1, "aos"))
        self.inst({"argv": ["aos-definitely-no-such-program"]})
        self.assertEqual(self.call(self.d)[:2], (127, "child"))

    def test_missing_json_is_aos_not_usage(self):
        self.assertEqual(self.call(os.path.join(self.d, "later.json"))[:2], (1, "aos"))

    def test_on_spawn_gets_the_popen_then_none(self):
        seen = []
        self.inst({"argv": ["sh", "-c", "exit 4"]})
        code, kind, _ = self.call(self.d, on_spawn=seen.append)
        self.assertEqual((code, kind), (4, "child"))
        self.assertEqual(len(seen), 2)
        self.assertIsInstance(seen[0], subprocess.Popen)
        self.assertIsNone(seen[1])

    def test_stderr_and_args_kwargs(self):
        p = self.write("args.sh", "#!/bin/sh\nprintf '<%s>' \"$@\" > got.txt; echo err >&2\n", executable=True)
        errp = os.path.join(self.d, "seen.err")
        code, kind, _ = self.call(p, stderr=errp, args=["a", "b c"])
        self.assertEqual((code, kind), (0, "child"))
        self.assertEqual(self.read("got.txt"), "<a><b c>")
        self.assertEqual(self.read("seen.err"), "err\n")

    def test_main_turns_kinds_into_exit_codes(self):
        """命令列才換算：usage→1（proto6 改）、aos→125、child→原樣。"""
        buf = io.StringIO()
        old, sys.stderr = sys.stderr, buf
        try:
            self.inst("{ 這不是 JSON")
            self.assertEqual(aos_exec.main([self.d]), 125)
            self.assertEqual(aos_exec.main([os.path.join(self.d, "沒這個")]), 1)
            self.inst({"argv": ["sh", "-c", "exit 1"]})
            self.assertEqual(aos_exec.main([self.d]), 1)
        finally:
            sys.stderr = old


class TestRunInstTimeout(ExecCase):
    """期限真的到才標記，不能拿 143／137 猜；stdout 仍保留已收的部分。"""

    def run_memory(self, script, timeout_ms=1000):
        inst = aos_inst.load_obj({"argv": [sys.executable, "-c", script]}, self.d)
        return aos_exec.run_inst(inst, "", timeout_ms=timeout_ms)

    def test_normal_exit_143_is_not_timeout_and_tuple_compatible(self):
        r = self.run_memory("print('正常'); raise SystemExit(143)")
        code, kind, out = r
        self.assertEqual(r, (143, "child", "正常\n"))
        self.assertEqual((code, kind, out), r)
        self.assertFalse(r.timed_out)

    def test_sigterm_timeout_keeps_output(self):
        r = self.run_memory("import time; print('已開始', flush=True); time.sleep(30)", 200)
        self.assertEqual(r, (143, "child", "已開始\n"))
        self.assertTrue(r.timed_out)

    def test_sigkill_timeout_keeps_output(self):
        r = self.run_memory("import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                            "print('已開始', flush=True); time.sleep(30)", 200)
        self.assertEqual(r, (137, "child", "已開始\n"))
        self.assertTrue(r.timed_out)

    def test_graceful_zero_exit_after_deadline_is_still_timeout(self):
        r = self.run_memory("import signal, sys, time; "
                            "signal.signal(signal.SIGTERM, lambda *args: sys.exit(0)); "
                            "print('已開始', flush=True); time.sleep(30)", 200)
        self.assertEqual(r, (0, "child", "已開始\n"))
        self.assertTrue(r.timed_out)

    def test_spawn_failure_is_not_timeout(self):
        inst = aos_inst.load_obj({"argv": ["aos-no-such-tool"]}, self.d)
        r = aos_exec.run_inst(inst, "", timeout_ms=1)
        self.assertEqual(r, (127, "child", ""))
        self.assertFalse(r.timed_out)


if __name__ == "__main__":
    unittest.main()
