"""核心給模組的三個小出口（方案 5.2）：tasks.json 項目的 `x` 照抄進 birth.json、lost 紀錄的 `never_started` 事實、
通用守門檔 `.aosd/stop-guard.json`。核心不知道它們的語意。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import unittest  # noqa: E402

from base import SLEEP, DaemonCase  # noqa: E402
from _matrix import MatrixCase  # noqa: E402
from aos7_fs import write_json  # noqa: E402


class TestX(MatrixCase):
    """〔core〕`x`：物件照抄進 birth.json（restart 也帶著）；不是物件＝那項不合、跳過；舊的 subroot／allow_stop 欄＝不合、指到子 daemon 包。"""

    def test_x_copied_to_birth(self):
        x = {"pack": "observe@1", "cfg": {"k": [1, 2]}}
        node = self.mknode("a", [{"name": "j", "argv": SLEEP, "x": x}])
        self.assertEqual(self.itick()["started"], ["j#1"])
        self.assertEqual(self.birth(node, "j")["x"], x)

    def test_bad_x_and_old_subroot_skipped(self):
        node = self.mknode("a", [{"name": "b", "argv": ["true"], "x": [1]},
                                 {"name": "s", "argv": ["true"], "subroot": "a/s"},
                                 {"name": "ok", "argv": ["true"]}])
        self.assertEqual(self.itick()["started"], ["ok#1"])
        errs = " ".join(self.round_json(node).get("tasks_error", []))
        self.assertIn("x 要是物件", errs)
        self.assertIn("子 daemon 包", errs)


class TestNeverStarted(MatrixCase):
    """〔core〕事實出口：lost 時 birth 沒有 runner、沒有 pid.json、out.log 不存在或空 → exit.json 與總結 ended 帶 never_started。"""

    def test_never_started_on_crash_after_birth(self):
        node = self.mknode("a", [{"name": "o", "mode": "once", "argv": ["true"]}])
        self.crash("aos7-tick", "after-birth")       # birth.json 寫了，runner 沒起
        sums = []
        for _ in range(3):
            sums.append(self.itock())
            self.itick()
        sums.append(self.itock())
        lost = [e for e in self.ends_of(sums, "o") if e.get("lost")]
        self.assertEqual(lost, [{"run": "o#1", "code": None, "lost": True, "never_started": True}])

    def test_no_never_started_when_task_ran(self):
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        self.kill_runner_and_task(node, "k")
        self.itick()
        sums = [self.itock()]
        lost = [e for e in self.ends_of(sums, "k") if e.get("lost")]
        self.assertEqual(lost, [{"run": "k#1", "code": None, "lost": True}])


class TestStopGuard(DaemonCase):
    """〔core〕通用守門檔：存在而 allow 不是 true（讀不到、壞掉也算）→ 控制檔 stop 回 ok:false（帶 note）；SIGTERM 照停。"""

    def guard(self, content):
        path = os.path.join(self.root, ".aosd", "stop-guard.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if isinstance(content, str):
            with open(path, "w") as f:
                f.write(content)
        else:
            write_json(path, content)

    def test_guard_blocks_then_allows(self):
        self.mknode("a")
        self.guard({"allow": False, "note": "屬於某某"})
        p = self.start_daemon(register=["a"])
        r = self.wait_receipt(self.ctl("stop"))
        self.assertIs(r["result"]["ok"], False)
        self.assertIn("屬於某某", r["result"]["msg"])
        self.guard("{")                                   # 壞掉＝不允許
        r = self.wait_receipt(self.ctl("stop"))
        self.assertIs(r["result"]["ok"], False, r["result"])
        self.assertIsNone(p.poll())
        self.guard({"allow": True})
        r = self.wait_receipt(self.ctl("stop"))
        self.assertIs(r["result"]["ok"], True, r["result"])
        self.assertEqual(p.wait(15), 0)

    def test_sigterm_ignores_guard(self):
        self.mknode("a")
        self.guard({"allow": False})
        p = self.start_daemon(register=["a"])
        self.wait_round(1)
        p.terminate()
        self.assertEqual(p.wait(15), 0)


if __name__ == "__main__":
    unittest.main()
