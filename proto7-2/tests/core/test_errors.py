"""錯誤四分支（spec §0）的核心測試：tasks.json 寫入照三態（G1）、tick 的非 3 失敗不是一回合（G2）、
「存在但不是一般檔＝不知道」對別人寫給核心的檔（tasks.json、timeline.json）也成立（頂層定案 3）。
"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import json  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import unittest  # noqa: E402
from unittest.mock import patch  # noqa: E402

from base import BIN, SLEEP, DaemonCase  # noqa: E402
from _matrix import MatrixCase, alive, fault, gen  # noqa: E402
import aos7_daemon_timeline  # noqa: E402
from aos7_fs import write_json  # noqa: E402

ITEM = '{"name": "x", "argv": ["true"]}'
HALF = '{"tasks": [{"name": "a", "argv": ["true"]}, {"name": "b"'


def tasks_path(node):
    return os.path.join(node, ".aos", "tasks.json")


def snapshot(path):
    """檔案現況：一般檔回內容 bytes，FIFO 回 "fifo"。"""
    import stat
    if stat.S_ISFIFO(os.lstat(path).st_mode):
        return "fifo"
    with open(path, "rb") as f:
        return f.read()


class TestTasksWriteG1(MatrixCase):
    """〔core〕G1：寫 tasks.json 的人讀舊內容照三態——讀不到或壞掉＝不知道＝拒寫，不能當空表把整份換掉。"""

    def _add_refused(self, kind):
        """tasks.json 半寫／被換成 FIFO／讀不到（EIO 注入）時 `aos7-ctl add` 拒寫：退出碼非 0、說明原因、檔案原封不動。"""
        node = self.mknode("a")
        tp = tasks_path(node)
        if kind == "half":
            with open(tp, "w") as f:
                f.write(HALF)
        elif kind == "fifo":
            os.remove(tp)
            os.mkfifo(tp)
        before = snapshot(tp)
        cmd = [sys.executable, os.path.join(BIN, "aos7-ctl"), "add", node, ITEM]
        if kind == "eio":
            with fault("open:*/.aos/tasks.json:EIO"):
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        else:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(p.returncode, 0, "壞掉的 tasks.json 還是寫了：%s" % p.stdout)
        self.assertIn("沒寫", p.stderr)
        self.assertEqual(snapshot(tp), before, "tasks.json 被改了")

    def test_add_to_missing_table_creates_it(self):
        """對照：tasks.json 不存在＝空表，照常加。"""
        node = self.mknode("a")
        os.remove(tasks_path(node))
        self.prog("aos7-ctl", "add", node, ITEM)
        self.assertEqual([i["name"] for i in self.tasks(node)], ["x"])


gen(TestTasksWriteG1, "add_refused", [(k, (k,)) for k in ("half", "fifo", "eio")], TestTasksWriteG1._add_refused)


class TestNotRegularInput(MatrixCase):
    """〔core〕頂層定案 3：別人寫給核心的檔（tasks.json、timeline.json）存在但不是一般檔＝不知道（以前當不存在）。"""

    def test_tasks_fifo_starts_nothing_deletes_nothing(self):
        """tasks.json 換成 FIFO：這回合不起、記 tasks_error；tock 不知道表上有誰，不刪槽。"""
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        self.itick()
        self.settle(node, "j")
        self.itock()
        tp = tasks_path(node)
        os.remove(tp)
        os.mkfifo(tp)
        for _ in range(3):
            out = self.itick()
            self.assertEqual(out["started"], [])
            self.assertTrue(any("不是一般檔" in e for e in self.round_json(node).get("tasks_error", [])),
                            self.round_json(node))
            self.itock()
        self.assertTrue(os.path.isdir(self.slot(node, "j")), "不知道表上有誰時刪了槽")

    def test_timeline_fifo_uses_defaults_and_notes(self):
        """timeline.json 換成 FIFO：用預設並回一筆說明（時間線記進 last_error）。"""
        node = self.mknode("a")
        tp = os.path.join(node, ".aos", "timeline.json")
        os.remove(tp)
        os.mkfifo(tp)
        ms, early, tmo, err = aos7_daemon_timeline.read_config(node)
        self.assertEqual((ms, early), (aos7_daemon_timeline.DEFAULT_INTERVAL_MS, False))
        self.assertIn("不是一般檔", err or "")


class TestTimelineConfig(DaemonCase):
    """〔core〕壞設定用預設並記錯；時間線仍開回合，修好後繼續。"""

    def test_interval_huge_int(self):
        node = self.mknode("a")
        for ms in (10 ** 309, -10 ** 309):
            with self.subTest(ms=ms):
                write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": ms})
                actual, _, _, err = aos7_daemon_timeline.read_config(node)
                self.assertEqual(actual, aos7_daemon_timeline.DEFAULT_INTERVAL_MS)
                self.assertTrue(err)

    def test_invalid_optional_config(self):
        node = self.mknode("a")
        for key, value in (("action_timeout_s", "x"), ("early_tock", "yes")):
            with self.subTest(key=key):
                write_json(os.path.join(node, ".aos", "timeline.json"), {key: value})
                ms, early, tmo, err = aos7_daemon_timeline.read_config(node)
                self.assertEqual((ms, early, tmo), (aos7_daemon_timeline.DEFAULT_INTERVAL_MS,
                                                  False, aos7_daemon_timeline.ACTION_TIMEOUT))
                self.assertIn(key, err or "")
        with patch.object(aos7_daemon_timeline, "fact", side_effect=OverflowError):
            ms, early, tmo, err = aos7_daemon_timeline.read_config(node)
            self.assertEqual((ms, early, tmo), (1000, False, 30.0))
            self.assertTrue(err)

    def test_huge_interval_daemon_recovers(self):
        node = self.mknode("a")
        with open(os.path.join(node, ".aos", "timeline.json"), "w") as f:
            json.dump({"interval_ms": 10 ** 309}, f)
        self.mknode("b", interval_ms=50)
        self.start_daemon(register=["a", "b"])
        self.wait_round(2, "a")
        self.wait_round(2, "b")
        self.assertEqual((self.nstat("a").get("last_error") or {}).get("where"), "timeline")
        self.assertEqual(self.nstat("a").get("interval_ms"), aos7_daemon_timeline.DEFAULT_INTERVAL_MS)
        before = self.node_round("a")
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": 50})
        self.wait_round(before + 2, "a")
        self.wait_for(lambda: self.nstat("a").get("interval_ms") == 50)


@unittest.skipIf(os.geteuid() == 0, "root 不受權限限制")
class TestTickFailureG2(DaemonCase):
    """〔core〕G2：tick 的非 3 失敗（例外、退出碼 1）不是一個回合——退避重試，不扣 resume --rounds 的倒數。"""

    def test_readonly_aos_does_not_eat_rounds(self):
        node = self.mknode("a", interval_ms=100)
        aos = os.path.join(node, ".aos")
        self.addCleanup(os.chmod, aos, 0o755)
        self.start_daemon(register=["a"])
        self.wait_round(2)
        self.wait_receipt(self.ctl("pause", "a", "--owner", "X"))
        self.wait_for(lambda: self.nstat().get("phase") == "paused", 10)
        r0 = self.node_round()
        os.chmod(aos, 0o555)
        self.wait_receipt(self.ctl("resume", "a", "--owner", "X", "--rounds", "3"))
        self.wait_for(lambda: (self.nstat().get("last_error") or {}).get("where") == "tick", 10, "tick 沒失敗")
        time.sleep(1.5)
        st = self.nstat()
        self.assertEqual(st.get("steps_left"), {"X": 3}, "tick 失敗卻扣了 rounds 倒數：%r" % st)
        self.assertEqual(st.get("paused_by"), [], "tick 失敗被當成回合，又被 pause 回去：%r" % st)
        self.assertEqual(self.round_json(node).get("round"), r0, "唯讀時回合數變了")
        os.chmod(aos, 0o755)
        self.wait_for(lambda: self.nstat().get("paused_by") == ["X"] and not self.nstat().get("steps_left"), 30,
                      "修好之後沒照 rounds 3 跑完再 pause：%r" % self.nstat())
        self.assertEqual(self.round_json(node).get("round"), r0 + 3)


if __name__ == "__main__":
    unittest.main()
