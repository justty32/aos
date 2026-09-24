"""astra 審查的 daemon 修正（09-24）：P6 交接用的摘要三態、P5 寫／刪失敗後自己收斂、P9 每圈只看有事的池。"""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

import aos_daemon
import aos_daemon_loop
import aos_daemon_pools
import aos_home

from _daemon_util import DaemonCase, wait_for


class SummaryStateTest(unittest.TestCase):
    """P6：只有「確定不存在」才是 gone；讀不到、壞、不是物件都是 unknown。pool_summary 照舊寬鬆。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-daemon-test-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.pool = self.home / "pools" / "p"

    def state(self, name="p"):
        return aos_daemon.pool_summary_state(self.home, name)

    def put(self, text):
        self.pool.mkdir(parents=True, exist_ok=True)
        (self.pool / "summary.json").write_text(text)

    def test_gone(self):
        self.assertEqual(self.state(), ("gone", None))                    # 連 pools/ 都沒有
        self.pool.mkdir(parents=True)
        self.assertEqual(self.state(), ("gone", None))                    # 池資料夾在、沒摘要
        (self.home / "pools" / "f").write_text("x")                       # 「池資料夾」是個檔案
        self.assertEqual(self.state("f"), ("gone", None))
        self.assertEqual(self.state(".."), ("gone", None))                # 不合法的名字 daemon 永遠不建
        self.assertIsNone(aos_daemon.pool_summary(self.home, "p"))

    def test_ok(self):
        self.put('{"pool": "p", "count": 2, "running": 1}')
        self.assertEqual(self.state(), ("ok", {"pool": "p", "count": 2, "running": 1}))
        self.assertEqual(aos_daemon.pool_summary(self.home, "p")["count"], 2)

    def test_unknown(self):
        for text in ("{bad", "[1, 2]", "null", '{"x": NaN}', "\udcff"):
            with self.subTest(text=text):
                if text == "\udcff":
                    self.pool.mkdir(parents=True, exist_ok=True)
                    (self.pool / "summary.json").write_bytes(b"\xff\xfe")
                else:
                    self.put(text)
                self.assertEqual(self.state(), ("unknown", None))
                self.assertIsNone(aos_daemon.pool_summary(self.home, "p"))   # 顯示用的照舊回 None
        (self.pool / "summary.json").unlink()
        (self.pool / "summary.json").mkdir()                                 # 是資料夾：讀不到
        self.assertEqual(self.state(), ("unknown", None))
        (self.pool / "summary.json").rmdir()
        with mock.patch.object(Path, "read_bytes", side_effect=PermissionError(13, "denied")):
            self.assertEqual(self.state(), ("unknown", None))
        with mock.patch.object(Path, "read_bytes", side_effect=OSError(5, "EIO")):
            self.assertEqual(self.state(), ("unknown", None))
        with mock.patch.object(Path, "read_bytes", side_effect=NotADirectoryError(20, "x")):
            self.assertEqual(self.state(), ("gone", None))


class RecoverTest(DaemonCase):
    """P5：摘要寫不進、刪池刪不掉時留著待辦，恢復後不重開 daemon 也會收斂；錯誤只印一次。"""

    def setUp(self):
        super().setUp()
        if os.geteuid() == 0:
            self.skipTest("root 不受資料夾權限限制")

    def lock(self, path):
        os.chmod(path, 0o555)
        def unlock():
            if path.exists():
                os.chmod(path, 0o755)
        self.addCleanup(unlock)

    def test_summary_write_failure_retried_after_recovery(self):
        target = self.targets(1, "normal")
        self.start()
        self.ok(self.scale(count=1, target=target))
        self.running("p", 1)
        pool = self.home / "pools" / "p"
        self.lock(pool)                                            # kids/ 自己的權限不變，照樣寫得進
        self.ok(self.call("kill", {"pool": "p", "names": ["0"]}))
        wait_for(lambda: (self.kid("p", 0) or {}).get("gen") == 2 and self.kid("p", 0)["state"] == "running")
        time.sleep(.1)                                             # 之後沒有別的事件
        before = self.summary()
        os.chmod(pool, 0o755)
        restored = time.time()
        fresh = wait_for(lambda: (self.summary() or {}).get("updated", 0) >= restored and self.summary())
        self.assertGreater(fresh["updated"], before["updated"])
        self.assertEqual(fresh["running"], 1)
        failures = [line for line in self.log().splitlines() if "summary.json" in line]
        self.assertEqual(len(failures), 1, self.log())             # 失敗期間每圈重試，只印一次
        self.halt()

    def test_remove_failure_retried_after_recovery(self):
        self.set_info(stop_wait_ms=600)
        target = self.targets(1, "term")                          # 不理 stop：收掉要等 stop_wait_ms
        self.start()
        self.ok(self.scale(count=1, target=target))
        self.running("p", 1)
        pool = self.home / "pools" / "p"
        self.ok(self.scale(count=0))                               # pool.json 寫完才鎖
        self.lock(pool)
        self.assertEqual(self.kid("p", 0)["state"], "killing")
        wait_for(lambda: self.kid("p", 0) is None)                 # 收完（kids/ 的檔刪得掉）
        time.sleep(.2)                                             # 好幾圈都刪不掉
        self.assertTrue((pool / "summary.json").exists())
        self.assertNotIn("p", self.ok(self.call("ls"))["pools"])   # 記憶體裡已經沒這池
        os.chmod(pool, 0o755)
        wait_for(lambda: not pool.exists())
        failures = [line for line in self.log().splitlines() if "拿不掉池" in line]
        self.assertEqual(len(failures), 1, self.log())
        self.halt()

class TodoTest(unittest.TestCase):
    """P9：每圈只重算／發布登記過的池；閒著的 2000 池一圈不碰。"""

    def test_idle_pools_not_scanned(self):
        with tempfile.TemporaryDirectory(prefix="aos-daemon-test-") as tmp:
            home = Path(tmp)
            aos_home.ensure_queue(home)
            (home / "pools").mkdir()
            owner = aos_daemon.Daemon(home, dict(aos_daemon.INFO_DEFAULTS), budget=0)   # 預算 0：不拉
            with mock.patch.object(aos_daemon_pools.Pool, "write_summary", return_value=True):
                for i in range(2000):
                    decl = {"pool": "p%d" % i, "owner": "/k", "count": 1, "skip": [], "ver": 1,
                            "target": "/nonexistent/{name}"}
                    owner.pools[decl["pool"]] = owner.new_pool(decl)
                self.assertEqual((len(owner.todo[0]), len(owner.todo[1])), (2000, 2000))
                owner.step()
            self.assertEqual(owner.todo, ({}, {}))
            self.assertEqual(len(owner.rotation), 2000)
            calls = []
            real_reconcile = owner.reconcile
            with mock.patch.object(aos_daemon_pools.Pool, "write_summary",
                                   lambda pool, now: calls.append(pool.name) or True), \
                    mock.patch.object(owner, "reconcile", lambda pool: calls.append("r:" + pool.name)
                                      or real_reconcile(pool)):
                owner.step()
                self.assertEqual(calls, [])                          # 沒事的池一個都不碰
                owner.pools["p7"].changed = True
                owner.pools["p9"].dirty = True
                owner.step()
                self.assertEqual(calls, ["r:p9", "p7"])
                calls.clear()
                owner.step()
                self.assertEqual(calls, [])
            # 規模感：閒著時一圈的時間跟池數無關（2000 池也遠低於掃一遍的成本）
            start = time.perf_counter()
            for _ in range(50):
                owner.step()
            self.assertLess((time.perf_counter() - start) / 50, .01)

    def test_rotation_is_deque(self):
        owner = aos_daemon.Daemon("/nonexistent", dict(aos_daemon.INFO_DEFAULTS), budget=10)
        self.assertTrue(hasattr(owner.rotation, "popleft"))

    def test_summary_write_failure_keeps_pool_in_todo(self):
        with tempfile.TemporaryDirectory(prefix="aos-daemon-test-") as tmp:
            home = Path(tmp)
            owner = aos_daemon.Daemon(home, dict(aos_daemon.INFO_DEFAULTS), budget=0)
            decl = {"pool": "p", "owner": "/k", "count": 1, "skip": [], "ver": 1, "target": "/x/{name}"}
            pool = owner.pools["p"] = owner.new_pool(decl)
            with mock.patch("aos_daemon_pools.log") as log:
                owner.publish()                                    # pools/p 不在：寫不進
                owner.publish()
                self.assertTrue(pool.changed)
                self.assertIn(pool, owner.todo[1])
                self.assertEqual(log.call_count, 1)
            (home / "pools" / "p").mkdir(parents=True)
            owner.publish()
            self.assertFalse(pool.changed)
            self.assertEqual(owner.todo[1], {})
            self.assertEqual(aos_daemon.pool_summary_state(home, "p")[0], "ok")

    def test_remove_failure_stays_pending_until_success(self):
        with tempfile.TemporaryDirectory(prefix="aos-daemon-test-") as tmp:
            home = Path(tmp)
            (home / "pools" / "p" / "kids").mkdir(parents=True)
            for leaf in ("summary.json", "pool.json"):
                (home / "pools" / "p" / leaf).write_text("{}")
            owner = aos_daemon.Daemon(home, dict(aos_daemon.INFO_DEFAULTS), budget=0)
            owner.pools["p"] = owner.new_pool({"pool": "p", "owner": "/k", "count": 0, "skip": [], "ver": 1})
            real, fails = os.unlink, [2]
            def unlink(path, *a, **k):
                if Path(path).name == "pool.json" and fails[0]:
                    fails[0] -= 1
                    raise PermissionError(13, "denied")
                return real(path, *a, **k)
            with mock.patch("aos_daemon_pools.os.unlink", unlink), mock.patch("aos_daemon_pools.log") as log:
                owner.publish()
                self.assertNotIn("p", owner.pools)
                self.assertEqual(owner.removing, {"p"})
                self.assertEqual(aos_daemon.pool_summary_state(home, "p"), ("gone", None))   # summary 先刪
                self.assertTrue((home / "pools" / "p" / "pool.json").exists())
                owner.publish()
                self.assertEqual(owner.removing, {"p"})
                owner.publish()
                self.assertEqual(owner.removing, set())
                self.assertEqual(log.call_count, 1)
            self.assertFalse((home / "pools" / "p").exists())

    def test_new_declaration_cancels_pending_removal(self):
        """待刪中又宣告同名池：取消待刪，不然下一圈的重試會刪掉新池的檔。"""
        with tempfile.TemporaryDirectory(prefix="aos-daemon-test-") as tmp:
            home = Path(tmp)
            aos_home.ensure_queue(home)
            (home / "pools").mkdir()
            owner = aos_daemon.Daemon(home, dict(aos_daemon.INFO_DEFAULTS), budget=5)
            owner.removing.add("p")
            self.assertEqual(owner.scale({"pool": "p", "owner": "/k", "count": 0}),
                             {"pool": "p", "count": 0, "ver": 0})            # count 0 不建池：待刪照舊
            self.assertEqual(owner.removing, {"p"})
            owner.scale({"pool": "p", "owner": "/k", "count": 1, "target": "/x/{name}"})
            self.assertEqual(owner.removing, set())
            owner.publish()
            self.assertTrue((home / "pools" / "p" / "pool.json").exists())
            self.assertEqual(aos_daemon.pool_summary_state(home, "p")[1]["count"], 1)


if __name__ == "__main__":
    unittest.main()
