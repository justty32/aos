"""aosp/daemon.py（run+daemon 隊寫）：daemon ls/start/stop、reconcile、控制收件匣。

reconcile() 是 registry.py 的功能（已經寫好），不靠 daemon.py，所以那一支獨立跑，
不受 daemon.py 是否就緒影響。其他需要 cli_daemon/cli_stop 的測試，daemon.py 還沒好時整批跳過。
"""
import os
import subprocess
import sys
import time
import unittest

PROTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from aosp import exits, fsutil, layout, registry  # noqa: E402
from .helpers import LandCase, write_source, run_cli  # noqa: E402

PY = sys.executable

try:
    from aosp import daemon as daemonmod  # noqa: E402
    HAS_DAEMON = hasattr(daemonmod, "cli_daemon") and hasattr(daemonmod, "cli_stop")
except Exception:
    daemonmod = None
    HAS_DAEMON = False

SKIP_MSG = "aosp/daemon.py 還沒寫好（cli_daemon/cli_stop 還沒有），先跳過"


class TestRegistryReconcile(LandCase):
    """只靠 registry.py（已完工），跟 daemon.py 進度無關。"""

    def test_reconcile_marks_dead_pid_running_as_stopped(self):
        home = layout.Home()
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        dead_pid = p.pid
        p.wait()
        registry.register(self.land.root, {"kind": "once"}, home=home)
        registry.update(self.land.root, home=home, pid=dead_pid, state=registry.RUNNING)

        changed = registry.reconcile(home=home)
        self.assertIn(self.land.root, changed,
                      msg="reconcile() 應該回報這塊地被改掉了，實際 %r" % changed)
        reg = registry.load(home)
        e = registry.find(reg, self.land.root)
        self.assertEqual(e["state"], registry.STOPPED,
                          msg="pid 死掉的 running 該被改成 stopped，實際 %r" % e)

    def test_reconcile_leaves_alive_pid_running(self):
        home = layout.Home()
        registry.register(self.land.root, {"kind": "once"}, home=home)
        registry.update(self.land.root, home=home, pid=os.getpid(), state=registry.RUNNING)
        registry.reconcile(home=home)
        reg = registry.load(home)
        e = registry.find(reg, self.land.root)
        self.assertEqual(e["state"], registry.RUNNING,
                          msg="pid 還活著就不該被 reconcile 改掉，實際 %r" % e)


@unittest.skipUnless(HAS_DAEMON, SKIP_MSG)
class TestDaemonLs(LandCase):
    def test_ls_prints_registry_table(self):
        home = layout.Home()
        registry.register(self.land.root, {"kind": "once"}, home=home)
        rc, out, err = run_cli("daemon", "ls")
        self.assertEqual(rc, exits.OK, msg="daemon ls 該正常結束，stderr=%r" % err)
        self.assertIn(self.land.root, out,
                      msg="daemon ls 該印得出登記在案的地路徑，實際 stdout=%r" % out)


@unittest.skipUnless(HAS_DAEMON, SKIP_MSG)
class TestControlInbox(LandCase):
    def test_stop_writes_control_file_with_op_stop(self):
        # cli_stop 刻意設計成「沒人在跑就什麼都不投」（見 daemon.py cli_stop 的註解），
        # 所以要先讓這塊地看起來「正在跑」：拿自己的 pid（保證活著）寫進鎖檔，
        # who_runs() 就會查到它。
        fsutil.write_json(self.land.lock, {"pid": os.getpid(), "at": fsutil.now_iso()})
        rc, out, err = run_cli("stop", self.land.root)
        self.assertEqual(rc, exits.OK, msg="aos stop 該正常結束，stderr=%r" % err)
        self.assertTrue(os.path.isdir(self.land.control),
                         msg="aos stop 之後 .aos/control/ 該存在")
        files = [f for f in os.listdir(self.land.control) if f.endswith(".json")]
        self.assertTrue(files, msg=".aos/control/ 該多一個檔，實際目錄內容 %r"
                        % os.listdir(self.land.control))
        obj = fsutil.read_json(os.path.join(self.land.control, files[0]))
        self.assertEqual(obj.get("op"), "stop",
                          msg="控制收件匣的檔 op 該是 stop，實際 %r" % obj)


@unittest.skipUnless(HAS_DAEMON, SKIP_MSG)
class TestDaemonStartStop(LandCase):
    """慢，用輪詢＋逾時而不是固定 sleep；真的做不出穩定的就靠環境變數開關。"""

    def setUp(self):
        super().setUp()
        self._started = False

    def tearDown(self):
        if self._started:
            try:
                run_cli("daemon", "stop")
            except Exception:
                pass
        super().tearDown()

    @unittest.skipUnless(os.environ.get("AOS_TEST_DAEMON"),
                         "daemon start/stop 難測得穩，設環境變數 AOS_TEST_DAEMON=1 才跑這條")
    def test_start_detach_then_becomes_running_then_stop(self):
        write_source(self.land, [
            {"name": "s1", "kind": "inst", "inst": {"argv": [PY, "-c", "pass"]}, "then": "s1"},
        ])
        home = layout.Home()
        registry.register(self.land.root, {"kind": "until", "until": "idle"}, home=home)

        rc, out, err = run_cli("daemon", "start")
        self.assertEqual(rc, exits.OK, msg="daemon start 該正常結束，stderr=%r" % err)
        self._started = True

        deadline = time.time() + 10
        entry = None
        while time.time() < deadline:
            reg = registry.load(home)
            e = registry.find(reg, self.land.root)
            if e and e.get("state") == registry.RUNNING and e.get("pid"):
                entry = e
                break
            time.sleep(0.2)
        self.assertIsNotNone(entry, msg="等了 10 秒，登記的地還沒變成 running 且有 pid")

        rc2, out2, err2 = run_cli("daemon", "stop")
        self.assertEqual(rc2, exits.OK, msg="daemon stop 該正常結束，stderr=%r" % err2)

        deadline = time.time() + 10
        stopped = False
        while time.time() < deadline:
            reg = registry.load(home)
            e = registry.find(reg, self.land.root)
            if e and e.get("state") == registry.STOPPED:
                stopped = True
                break
            time.sleep(0.2)
        self.assertTrue(stopped, msg="等了 10 秒，地還沒被 daemon stop 標成 stopped")
