"""固定回歸矩陣（四）：不起 daemon 的零散項（A2-04 同程序部分、A2-07、A2-08、A2-10、A2-12）。

**AOS7_TEST_* 環境變數只給測試用**（這裡用 `AOS7_TEST_CRASH=tmp:last-round.json`：原子寫的暫存檔寫好、rename 之前 SIGKILL）。

矩陣維度與判定：

1. **node 本身是符號連結**（同程序 tick／tock）→ tick／tock 回 gone（O_NOFOLLOW），連結目標裡沒建 `.aos`。上層是連結的案已刪（誤用 M-2.1）。
2. **A2-07 暫存檔清理** × 情境 ∈ {放好的死 pid 暫存（`.aos/`、槽裡）＋活 pid 暫存、`tmp:last-round.json` 連殺 5 次 tock}
   → tick＋tock 後死的被清、活的留著；連殺後再正常 tock，`.aos/` 底下沒有 `.tmp.` 殘留。
3. **A2-08 診斷不截掉前綴**：`Timeline.err(..., kind=)` 的 err 以 kind 開頭、≤ 320 字、帶 kind；starttime 讀不到的任務在 tock 總結
   `errors` 留 `phase: "unsure"`。
4. **A2-10**：history module 的 `--max-lines` 也套在 `daemon-events.jsonl`——已搬到 modules/tests/test_modules_history.py。
5. **A2-12**：tock 寫 last-round.json 早於任何 tock.json（任務收到 tock 時已經讀得到這回合的總結）。
"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import os
import shutil
import tempfile
import unittest
from unittest import mock

from base import SLEEP
from _matrix import MatrixCase, dead_pid, gen
import aos7_daemon_timeline
import aos7_fs
import aos7_proc
import aos7_tock
from aos7_fs import write_json


class _FakeDaemon:
    def __init__(self, root):
        self.root = root


class TestSymlinkInProcess(MatrixCase):
    """〔core〕"""
    def _symlink(self, where):
        """node 本身是符號連結（指到 root 外）：tick／tock 回 gone，連結目標裡沒被建 `.aos`。"""
        out = tempfile.mkdtemp(prefix="aos72-matrix-out-")
        self.addCleanup(shutil.rmtree, out, True)
        os.symlink(out, os.path.join(self.root, "a"))
        r = self.itick("a")
        self.assertTrue(r.get("gone"), "符號連結的 node 照樣開了回合：%r" % r)
        self.assertTrue(self.itock("a").get("gone"))
        self.assertFalse(os.path.exists(os.path.join(out, ".aos")), "寫進了 root 外的連結目標")


gen(TestSymlinkInProcess, "symlink_node", [("self", ("self",))], TestSymlinkInProcess._symlink)


class TestTmpSweep(MatrixCase):
    """〔core〕"""
    def test_dead_writer_tmp_cleared_live_kept(self):
        node = self.mknode("a", [{"name": "j", "argv": ["true"]}])
        self.itick()
        self.settle(node, "j")
        self.itock()
        dead = dead_pid()
        aos = os.path.join(node, ".aos")
        files = {os.path.join(aos, ".last-round.json.tmp.%d" % dead): False,
                 os.path.join(self.slot(node, "j"), ".exit.json.tmp.%d" % dead): False,
                 os.path.join(aos, ".x.json.tmp.%d" % os.getpid()): True}
        for p in files:
            with open(p, "w") as f:
                f.write("{")
        self.itick()
        self.settle(node, "j")
        self.itock()
        for p, keep in files.items():
            self.assertEqual(os.path.exists(p), keep, "%s：%s" % ("活的寫者的暫存被刪了" if keep else "死 pid 的暫存沒清", p))

    def test_crash_before_rename_leaves_nothing(self):
        node = self.mknode("a")
        self.itick()
        self.itock()
        self.itick()
        for _ in range(5):
            self.crash("aos7-tock", "tmp:last-round.json")
        self.assertIs(self.round_json(node)["open"], True)
        self.itock()
        left = [os.path.join(d, n) for d, _ds, ns in os.walk(os.path.join(node, ".aos")) for n in ns if ".tmp." in n]
        self.assertEqual(left, [], "暫存檔殘留")


class TestDiagnostics(MatrixCase):
    """〔diag〕status／總結的診斷欄（A2-08，F53）。"""
    def test_timeline_err_keeps_kind_prefix(self):
        os.makedirs(os.path.join(self.root, "a"))
        tl = aos7_daemon_timeline.Timeline(_FakeDaemon(self.root), "a", None)
        tl.err("action-lock", None, "stale-holder-unverified：" + "x" * 2000, kind="stale-holder-unverified")
        e = tl.last_error
        self.assertTrue(e["why"].startswith("stale-holder-unverified"), e["why"][:80])
        self.assertLessEqual(len(e["why"]), 320)
        self.assertEqual(e.get("kind"), "stale-holder-unverified")

    def test_unsure_in_tock_errors(self):
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.itick()
        self.wait_pid(node, "k")
        self.itock()
        self.itick()
        with mock.patch.object(aos7_proc, "proc_starttime", lambda pid: None), \
                mock.patch.object(aos7_fs, "proc_starttime", lambda pid: None):
            lr = self.itock()
        self.assertIn("k#1", lr["alive"])
        self.assertTrue([x for x in self.errors_for(lr, "k") if x.get("kind") == "unsure" and x.get("why")],
                        "starttime 讀不到的任務沒在 errors 留 unsure：%r" % lr.get("errors"))


class TestTockOrder(MatrixCase):
    """〔core〕"""
    def test_last_round_written_before_tock_json(self):
        node = self.mknode("a", [{"name": "k", "mode": "keep", "argv": SLEEP}])
        self.itick()
        self.wait_pid(node, "k")
        order = []
        real = aos7_tock.write_json

        def rec(path, obj):
            order.append(os.path.basename(path))
            return real(path, obj)
        with mock.patch.object(aos7_tock, "write_json", rec):
            self.itock()
        self.assertIn("tock.json", order)
        self.assertIn("last-round.json", order)
        self.assertLess(order.index("last-round.json"), order.index("tock.json"), order)


if __name__ == "__main__":
    unittest.main()
