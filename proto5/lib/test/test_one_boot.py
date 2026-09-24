"""one-boot（2026-09-24）：daemon 開 tick、同時一格、sqlite 帳本、aos up／down 的崩潰與時序。

真 daemon＋真 tick。要 tick 停在「帳本交易提交前」時，daemon 的環境帶 AOS_KERNEL_CRASH_*（aos_kernel_store.crash_hook），
只有「這筆交易要寫進某個行程」的那一格會停、而且只停一次；停住後由測試 kill -9。
"""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time

import aos_client
import aos_daemon_ticks
import aos_home
import aos_kernel_store
from _kernel_util import CLI, PY, KernelCase, read_json, wait_for


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return Path("/proc/%d/stat" % pid).read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


class OneBootCase(KernelCase):
    def start_daemon(self, env=None):
        log = open(self.root / "daemon.log", "ab")
        self.addCleanup(log.close)
        self.daemon_process = subprocess.Popen(
            [PY, str(CLI / "aos-daemon"), "boot", "--target", str(self.daemon)], env=dict(os.environ, **(env or {})),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
        wait_for(lambda: self.dstate().get("pid") == self.daemon_process.pid)
        return self.daemon_process

    def hang_env(self, proc):
        self.flag = self.root / "hang.flag"
        return {"AOS_KERNEL_CRASH_AT": "before-commit", "AOS_KERNEL_CRASH_PROC": proc,
                "AOS_KERNEL_CRASH_FLAG": str(self.flag)}

    def hung_pid(self, timeout=8):
        wait_for(lambda: self.flag.exists() and self.flag.read_text().strip(), timeout=timeout)
        return int(self.flag.read_text())

    def submit_add(self, name, **params):
        target = self.job("pass", name)
        return aos_client.submit(self.home, "add", dict(target=target, name=name, interval_ms=3600000, **params))

    def registration(self):
        return aos_daemon_ticks.peek(self.daemon, self.home)

    def daemon_log(self):
        path = self.root / "daemon.log"
        return path.read_text(errors="replace") if path.exists() else ""


class LedgerTransaction(OneBootCase):
    def test_kill9_inside_ledger_transaction_rolls_back(self):
        """tick 寫帳本寫到一半被 kill -9：整筆沒發生，下一格重判同一張原單，只登記一次、只回一次。"""
        self.initialize()
        self.start_daemon(self.hang_env("job"))
        self.boot()
        name = self.submit_add("job")
        pid = self.hung_pid()
        os.kill(pid, signal.SIGKILL)
        wait_for(lambda: not pid_alive(pid))
        state = self.state()
        self.assertNotIn("job", state["procs"])                         # 交易沒提交＝沒發生
        self.assertTrue((self.home / "requests" / name).exists())       # 原單還在，下一格重判
        self.assertFalse((self.home / "responses" / name).exists())
        response = aos_client.wait_response(self.home, name, timeout_ms=8000, poll_ms=5)
        self.assertEqual(response["result"]["name"], "job")
        self.assertIn("job", self.state()["procs"])
        conn = sqlite3.connect(aos_kernel_store.path_of(self.home))
        self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(conn.execute("SELECT count(*) FROM procs WHERE name='job'").fetchone()[0], 1)
        conn.close()
        self.assertIn("TickFailed", self.daemon_log())                  # 被砍的那格記一行
        wait_for(lambda: (self.registration() or {}).get("fails") == 0)  # 下一格成功就歸零

    def test_proc_entry_point(self):
        """aos-kernel proc NAME --json：查一筆（agent 用同一支 lib）；沒有退 1。"""
        self.setup_running()
        self.add(self.job("pass", "rep"), name="rep", interval_ms=3600000)
        out = json.loads(self.good_cli("proc", self.home, "rep", "--json").stdout)
        self.assertEqual(out["_metainfo"], {"_type": "aos_kernel_proc", "_version": 1})
        self.assertTrue(out["found"])
        self.assertEqual(out["proc"]["target"], str(self.root / "rep.json"))
        missing = self.cli("proc", self.home, "nope", "--json")
        self.assertEqual(missing.returncode, 1)
        self.assertFalse(json.loads(missing.stdout)["found"])


class TickTimeout(OneBootCase):
    def test_stuck_tick_is_killed_counted_and_retried(self):
        """一格卡住超過 tick_timeout_ms：daemon 整組 KILL、記連敗、退避後再開；卡住那格的決定沒發生，重做一次。"""
        self.initialize(tick_timeout_ms=400)
        self.start_daemon(self.hang_env("slow"))
        self.boot()
        name = self.submit_add("slow")
        pid = self.hung_pid()
        wait_for(lambda: not pid_alive(pid), timeout=5)                  # 不用測試砍：daemon 逾時自己砍
        wait_for(lambda: "逾時" in self.daemon_log())
        response = aos_client.wait_response(self.home, name, timeout_ms=8000, poll_ms=5)
        self.assertEqual(response["result"]["name"], "slow")
        wait_for(lambda: (self.registration() or {}).get("fails") == 0)


class DaemonKilled(OneBootCase):
    def test_daemon_kill9_while_tick_running_then_restart(self):
        """daemon 被 kill -9 時有一格正卡著：那格變孤兒、還握著鎖；新 daemon 開的格拿不到鎖退 75（不算失敗），
        孤兒自己的鬧鐘（2×tick_timeout_ms）一到就死、鎖放開，帳本對得起來，cpu 由新 daemon 拉回來。"""
        self.initialize(tick_timeout_ms=1000)
        self.start_daemon(self.hang_env("orphan"))
        self.boot()
        self.wait_running("default", 1)
        name = self.submit_add("orphan")
        pid = self.hung_pid()
        old_cpu = self.kid_pid("default", 0)
        self.daemon_process.kill()
        self.daemon_process.wait(timeout=5)
        self.assertTrue(pid_alive(pid))                                    # 孤兒還在，鎖還在
        self.start_daemon()                                                # 同一個家、重開（不帶掛鉤）
        wait_for(lambda: self.kid_pid("default", 0) not in (None, old_cpu))
        wait_for(lambda: not pid_alive(pid), timeout=6)                   # 孤兒鬧鐘到了自己死
        response = aos_client.wait_response(self.home, name, timeout_ms=8000, poll_ms=5)
        self.assertEqual(response["result"]["name"], "orphan")
        self.assertIn(self.state()["procs"]["orphan"]["status"], ("queued", "running"))
        self.assertEqual(self.registration().get("fails"), 0)           # 退 75 不算失敗
        self.assertFalse(pid_alive(old_cpu))


class Failures(OneBootCase):
    def test_consecutive_failures_back_off_and_never_stop(self):
        """連續失敗：記 log、退避重試、不自己停；修好後連敗歸零、health 回 ok 那一類。"""
        self.setup_running()
        info = (self.home / "info.json").read_text()
        (self.home / "info.json").write_text("{壞掉")
        wait_for(lambda: (self.registration() or {}).get("fails", 0) >= 3, timeout=8)
        self.assertIsNone(self.daemon_process.poll())                    # daemon 沒停
        self.assertGreaterEqual(self.daemon_log().count("TickFailed"), 3)
        (self.home / "info.json").write_text(info)
        wait_for(lambda: (self.registration() or {}).get("fails") == 0, timeout=8)
        seq = self.state()["last_seq"]
        wait_for(lambda: self.state()["last_seq"] > seq)

    def test_health_reports_failing_ticks(self):
        """登記的 cli 每次都失敗：ls 第一行 health 報 tick 連敗、指去看 daemon 的 stderr。"""
        self.setup_running()
        response = aos_client.call(self.daemon, "tick", {"home": str(self.home), "cli": "/bin/false", "every_ms": 5},
                                   timeout_ms=5000, poll_ms=5)
        self.assertIn("result", response)
        wait_for(lambda: (self.registration() or {}).get("fails", 0) >= 2)
        head = self.good_cli("ls", self.home).stdout.splitlines()[0]
        self.assertIn("tick 連敗", head)
        data = json.loads(self.good_cli("ls", self.home, "--json").stdout)
        self.assertEqual(data["_metainfo"]["_version"], 3)
        self.assertEqual(data["health"]["code"], "stall")
        self.assertGreaterEqual(data["kernel"]["tick"]["fails"], 2)


class Triggers(OneBootCase):
    def test_new_request_triggers_tick_without_waiting_for_period(self):
        """tick_ms 60 秒：只有新檔才開格；投 add 一秒內處理到，閒著不空轉。"""
        self.initialize(tick_ms=60000)
        self.start_daemon()
        self.boot()
        seq = self.state()["last_seq"]
        time.sleep(1)
        self.assertLessEqual(self.state()["last_seq"], seq + 1)          # 閒著不空轉（最多一格收尾）
        started = time.monotonic()
        response = self.call("add", {"target": self.job("pass", "fast"), "name": "fast", "interval_ms": 3600000})
        self.assertEqual(response["result"]["name"], "fast")
        self.assertLess(time.monotonic() - started, 2)

    def test_one_tick_at_a_time(self):
        """鎖：外面手動跑的 tick 撞上 daemon 開的那格＝退 75，不會兩格同時改帳本。"""
        self.initialize()
        self.start_daemon(self.hang_env("held"))
        self.boot()
        self.submit_add("held")
        pid = self.hung_pid()
        result = self.cli("tick", self.home)
        self.assertEqual(result.returncode, 75, result.stderr)
        os.kill(pid, signal.SIGKILL)


class Down(OneBootCase):
    def aos(self, *args, timeout=40):
        env = dict(os.environ, AOS_KERNEL_HOME=str(self.home))
        return subprocess.run([PY, str(CLI / "aos"), *args], env=env, capture_output=True, text=True, timeout=timeout)

    def mine(self):
        me = str(self.root).encode()
        out = []
        for entry in os.listdir("/proc"):
            if entry.isdigit() and int(entry) != os.getpid():
                try:
                    if me in Path("/proc/%s/cmdline" % entry).read_bytes() and pid_alive(int(entry)):
                        out.append(int(entry))
                except OSError:
                    pass
        return out

    def test_aos_up_then_down_leaves_nothing(self):
        self.initialize()
        up = self.aos("up")
        self.assertEqual(up.returncode, 0, up.stderr)
        self.assertIn("up K=", up.stdout)
        self.assertTrue(self.registration())
        once = self.call("add", {"target": self.job("pass", "one"), "name": "one", "once": True})
        self.assertEqual(once["result"]["code"], 0, once)
        again = self.aos("up")                                            # 再跑一次也行（等於重 boot）
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("本來就在", again.stdout)
        down = self.aos("down")
        self.assertEqual(down.returncode, 0, down.stderr)
        self.assertIsNone(self.registration())                            # 停好那格自己撤登記
        wait_for(lambda: not self.mine(), timeout=10)
        self.assertEqual(self.state()["phase"], "stopped")

    def test_daemon_halt_kills_stuck_tick(self):
        """停 daemon 時有一格卡著：給 stop_wait_ms＋kill_wait_ms，再不退就 KILL 整組，daemon 才退出。"""
        self.initialize()
        self.start_daemon(self.hang_env("stuck"))
        self.boot()
        self.submit_add("stuck")
        pid = self.hung_pid()
        started = time.monotonic()
        aos_home.post_request(self.daemon, aos_client.new_name("stop"), {"jsonrpc": "2.0", "method": "stop"})
        self.assertEqual(self.daemon_process.wait(timeout=8), 0)
        self.assertLess(time.monotonic() - started, 5)
        wait_for(lambda: not pid_alive(pid))
        self.assertIsNotNone(self.registration())                          # 登記留著，下次開 daemon 照開


class Legacy(OneBootCase):
    def test_v2_state_json_is_imported_on_boot(self):
        """舊的第 2 版 K/state.json（kernel cpu 那一版）：boot 匯入 sqlite、改名 .v2-old；行程留著。"""
        self.initialize()
        self.start_daemon()
        old = {"chain": "1-1", "kcpu": "kernel/0", "cli": "/x", "last_seq": 9, "phase": "running", "halting": False,
               "pools": {}, "busy": {}, "on": {}, "recent": [], "ready": {"default": []}, "delayed": [], "stale": {},
               "procs": {"keep": {"request": "r.json", "target": self.job("pass", "keep"), "dir_target": ".aos/inst.json",
                                  "once": False, "pool": "default", "interval_ms": 3600000, "timeout_ms": 0,
                                  "status": "queued", "runs": 3, "fails": 0, "not_before": 0, "pending": None}},
               "acks": [], "replies": [], "deletes": [], "sends": [], "features": ["park"]}
        aos_home.write_json(self.home / "state.json", old)
        self.assertTrue(aos_kernel_store.legacy(self.home))
        tick = self.cli("tick", self.home)
        self.assertEqual(tick.returncode, 1)
        self.assertIn("LedgerVersion", tick.stderr)
        self.good_cli("boot", self.home, timeout=20)
        self.assertFalse((self.home / "state.json").exists())
        self.assertTrue((self.home / "state.json.v2-old").exists())
        state = self.state()
        self.assertEqual(state["procs"]["keep"]["runs"], 3)
        self.assertNotIn("kcpu", state)
        self.assertEqual(state["ticker"], str(self.daemon))
