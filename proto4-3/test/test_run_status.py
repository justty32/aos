"""aos-run 的兩個新旗標：`--status-fd N`（給程式看的事件流）與 `--stop-on-error`。

stderr 那些 `aos-run: …` 行是給人看的、照舊；status-fd 是給程式看的（daemon 讀的就是
它）——一行一個事件、`\\n` 結尾、寫完就到。
（`_util.py` 的坑：TestCase 裡別放叫 `run()` 的方法，那是 unittest 自己的。）
"""
import os
import signal
import subprocess
import unittest

from _util import PY
from test_run import RUN, RunCase, _reap

BROKEN = "{ 這不是 JSON"


class StatusFdCase(RunCase):

    def statuses(self, *args, with_fd=True, timeout=30):
        """開一個 aos-run、把 status 管子接起來，回 `(那些行, 退出碼, stderr)`。"""
        r, w = os.pipe()
        argv = [PY, RUN] + [str(a) for a in args]
        if with_fd:
            argv += ["--status-fd", str(w)]
        p = subprocess.Popen(argv, pass_fds=(w,), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        self.addCleanup(_reap, p)
        os.close(w)                             # 寫端只留給子進程，不然等不到 EOF
        with os.fdopen(r, encoding="utf-8") as f:
            lines = [line.rstrip("\n") for line in f]
        _out, err = p.communicate(timeout=timeout)
        return lines, p.returncode, err


class TestStatusFd(StatusFdCase):

    def test_event_order(self):
        """ready（裝好訊號處理器、還沒開跑）→ start #n → done #n → stop <原因>。"""
        self.inst({"argv": ["sh", "-c", "exit 0"]})
        lines, code, err = self.statuses(self.d, "--max-runs", 1)
        self.assertEqual(code, 0)
        self.assertEqual(lines[0], "ready")
        self.assertEqual(lines[1], "start #1")
        self.assertRegex(lines[2], r"^done #1 exit=0 kind=child \d+\.\ds$")
        self.assertEqual(lines[3], "stop max_runs")
        self.assertEqual(len(lines), 4)
        self.assertIn("aos-run: #1 exit=0", err)        # 給人看的那條照舊印

    def test_two_runs_are_numbered(self):
        self.inst({"argv": ["sh", "-c", "exit 3"]})
        lines, _code, _err = self.statuses(self.d, "--max-runs", 2, "--interval-ms", 50)
        self.assertEqual([l for l in lines if l.startswith("start")],
                         ["start #1", "start #2"])
        self.assertTrue(lines[-2].startswith("done #2 exit=3 kind=child "), lines)
        self.assertEqual(lines[-1], "stop max_runs")

    def test_aos_failures_are_kind_aos_and_exit_125(self):
        """inst.json 壞掉＝aos-exec 自己失敗：kind=aos，exit 報 125（跟子程式的碼分得開）。"""
        self.inst(BROKEN)
        lines, code, err = self.statuses(self.d, "--max-runs", 1)
        self.assertEqual(code, 0)
        self.assertRegex(lines[2], r"^done #1 exit=125 kind=aos ")
        self.assertIn("aos-run: #1 exit=125", err)

    def test_a_json_that_is_not_there_yet_is_kind_aos(self):
        """`.json` 還沒出現也是 aos 自己失敗（125），不是用法錯——檔案出現就跑起來。"""
        p = os.path.join(self.d, "later.json")
        lines, code, _err = self.statuses(p, "--max-runs", 1)
        self.assertEqual(code, 0)
        self.assertRegex(lines[2], r"^done #1 exit=125 kind=aos ")

    def test_ready_comes_after_the_signal_handlers_are_installed(self):
        """`ready` 是「訊號接得住了」的保證：一看到它就 SIGTERM，也是乾淨地退（0）。"""
        r, w = os.pipe()
        self.inst({"argv": ["sh", "-c", "exit 0"]})
        p = subprocess.Popen([PY, RUN, self.d, "--interval-ms", "60000",
                              "--status-fd", str(w)], pass_fds=(w,),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(_reap, p)
        os.close(w)
        f = os.fdopen(r, encoding="utf-8")
        self.addCleanup(f.close)
        self.assertEqual(f.readline().rstrip("\n"), "ready")
        p.send_signal(signal.SIGTERM)               # 裝好了才寫 ready，所以收得住
        _out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0)           # 不是 143（預設處置直接死）
        self.assertIn("aos-run: stop signal", err)

    def test_no_status_fd_writes_nothing(self):
        """沒給 --status-fd 就什麼都不寫（管子開著也一樣，讀到的就是空的）。"""
        self.inst({"argv": ["true"]})
        lines, code, err = self.statuses(self.d, "--max-runs", 1, with_fd=False)
        self.assertEqual((lines, code), ([], 0))
        self.assertIn("aos-run: stop max_runs", err)


class TestStopOnError(StatusFdCase):

    def test_stop_on_error_stops_at_the_first_aos_failure(self):
        self.inst(BROKEN)
        lines, code, err = self.statuses(self.d, "--stop-on-error", "--interval-ms", 50)
        self.assertEqual(code, 125)                     # 跟 aos-exec 的 125 同一個意思
        self.assertIn("aos-run: stop error", err)
        self.assertEqual(len(self.logs(err)), 1)        # 第一次就停，沒有第二次
        self.assertEqual(lines[-1], "stop error")

    def test_stop_on_error_does_not_stop_on_a_child_code(self):
        """子程式自己回非 0 不算 error——那是它的碼，不是 aos-exec 失敗。"""
        self.inst({"argv": ["sh", "-c", "exit 1"]})
        r = self.aos_run(self.d, "--stop-on-error", "--max-runs", 2, "--interval-ms", 50)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.logs(r.stderr)), 2)
        self.assertIn("aos-run: stop max_runs", r.stderr)

    def test_without_the_flag_it_keeps_trying(self):
        """沒給 --stop-on-error 就照舊不停（壞了也活著）。"""
        self.inst(BROKEN)
        r = self.aos_run(self.d, "--max-runs", 2, "--interval-ms", 50)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.logs(r.stderr)), 2)
        self.assertIn("aos-run: stop max_runs", r.stderr)


if __name__ == "__main__":
    unittest.main()
