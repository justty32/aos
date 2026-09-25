"""09-24 tick-gap（P2）的 kill -9 回歸：真 daemon＋真 cpu＋真 tick，只跑 sh 這種普通工作，不叫模型。

cpu 的 poll_ms 一律設 30000：cpu 睡著時只有門鈴（K/pools/<池>/cpus/<i>/wake）叫得醒它。
時序斷言只用「遠小於輪詢間隔」（輪詢 30 秒、斷言 10 秒內）；不看信箱／資料夾檔名順序。

1. daemon 被 kill -9 → 再 aos up：起得來（.daemon.lock 自己放）、帳本 integrity ok、
   新 cpu 的門鈴照樣叫得醒（一件 --once 工作 10 秒內跑完），舊 cpu 不會留下來搶單。
2. tick 卡在「第 8 步派的單已放、門鈴已按、提交點 C 還沒存」被 kill -9：cpu 照樣被門鈴叫醒做完，
   .tick.lock 自己放、下一格收回音回給等的人；工作只跑一次（沒派兩次、沒丟）、帳本 integrity ok。
3. tick 卡在「提交點 D 已存（派給誰記了）、還沒放單／按門鈴」被 kill -9：下一格靠 recent 補放並按門鈴，
   被叫醒的 agent 只多跑一次；帳本 integrity ok。

怎麼讓 tick 卡在指定的點：one-boot 的 AOS_KERNEL_CRASH_*（aos_kernel_store.crash_hook）只卡在
「某行程第一次出現在交易裡」那一筆提交前，卡不到 D、卡不到放單之後。所以這裡改用 daemon 的 tick 登記
（method tick 的 cli 可換）：boot 完把 cli 換成暫存目錄裡的一支包裝（TICK_GATE），它 import 真的
aos_kernel，只在 Kernel.post_dispatched 前後加一個「閘門檔寫了這個點名、就寫 pid 然後睡死」的掛鉤，
其餘照走真的 aos-kernel tick。一次性（寫過 pid 檔就不再卡）。

沒做的：on_bad 在判 bad 附近 tick 被 kill -9——test_tick_gap.BadNotice.test_crash_before_delivery_resends_once
已經蓋到（崩在提交點 B 之後、寄信之前；kill -9 跟那裡丟例外在帳本上一樣，都是 B 已存、letters 還沒清），不重複。
"""
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time

import aos_client
import aos_daemon_ticks
import aos_kernel_engine
import aos_kernel_store
from _kernel_util import CLI, PY, KernelCase, read_json, wait_for

POLL = {"poll_ms": 30000}
FAST = 10          # 秒：遠小於 cpu 的 30 秒輪詢

# 包裝的 aos-kernel：閘門檔（ROOT/gate）寫著點名時，到那個點就寫 pid 檔（ROOT/gate.pid）然後睡死等 kill -9。
TICK_GATE = r'''#!%(py)s
import os, sys, time
sys.path.insert(0, %(lib)r)
import aos_kernel_engine
from aos_kernel import main
GATE, FLAG = %(gate)r, %(flag)r

def hang(point):
    try:
        with open(GATE) as f:
            want = f.read().strip()
    except FileNotFoundError:
        return
    if want != point or os.path.exists(FLAG):
        return
    with open(FLAG + ".tmp", "w") as f:
        f.write(str(os.getpid()))
    os.replace(FLAG + ".tmp", FLAG)
    while True:
        time.sleep(1)

orig = aos_kernel_engine.Kernel.post_dispatched

def post_dispatched(self, keys=None):
    if keys:                                   # D 已存、這一輪新派的還沒放單
        hang("after-D")
    orig(self, keys)
    if keys is None and self.state["recent"]:  # 第 8 步派的已放單、按過門鈴；提交點 C 還沒
        hang("after-post")

aos_kernel_engine.Kernel.post_dispatched = post_dispatched
sys.exit(main())
'''


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    try:
        return Path("/proc/%d/stat" % pid).read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


class Kill9Case(KernelCase):
    PREFIX = "aos-tickgap-kill9-"

    def setUp(self):
        super().setUp()
        self.addCleanup(self.down)          # 先 aos down（後登記先跑），再由 KernelCase.cleanup 兜底砍殘留

    # ---- 開關機 ----

    def aos(self, *args, timeout=40):
        env = dict(os.environ, AOS_KERNEL_HOME=str(self.home))
        return subprocess.run([PY, str(CLI / "aos"), *args], env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=timeout)

    def up(self):
        result = self.aos("up")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def down(self):
        if (self.home / "info.json").exists():
            try:
                self.aos("down", "--wait-ms", "8000", timeout=30)
            except subprocess.TimeoutExpired:
                pass

    def mine(self):
        """命令列含這個暫存目錄、還活著的行程。"""
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

    # ---- 檢查 ----

    def integrity(self):
        conn = sqlite3.connect(aos_kernel_store.path_of(self.home))
        try:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            conn.close()

    def lock_free(self):
        """K/.tick.lock 拿得到（等最多 5 秒；daemon 的格也會搶，所以用等的）。"""
        fd = aos_kernel_engine.take_lock(self.home, wait_ms=5000)
        self.assertIsNotNone(fd, ".tick.lock 放不掉")
        os.close(fd)

    def counter_job(self, name, code=0):
        """每跑一次往 <name>.runs 加一行，然後退 code。"""
        runs = self.root / (name + ".runs")
        target = self.write(self.root / (name + ".json"),
                            {"argv": ["sh", "-c", 'echo x >> "$1"; exit %d' % code, "sh", str(runs)]})
        return target, runs

    def runs(self, path):
        return len(path.read_text().splitlines()) if path.exists() else 0

    # ---- 閘門 ----

    def install_gate(self, point):
        """把 daemon 的 tick 登記換成包裝版 aos-kernel；point 之後第一次到那個點就卡住。"""
        self.gate, self.flag = self.root / "gate", self.root / "gate.pid"
        script = self.root / "aos-kernel-gate"
        script.write_text(TICK_GATE % {"py": PY, "lib": str(CLI.parent / "lib"),
                                       "gate": str(self.gate), "flag": str(self.flag)})
        script.chmod(0o755)
        reg = aos_daemon_ticks.peek(self.daemon, self.home)
        params = {"home": str(self.home), "cli": str(script), "every_ms": reg["every_ms"], "timeout_ms": reg["timeout_ms"]}
        self.assertIn("result", aos_client.call(self.daemon, "tick", params, timeout_ms=5000, poll_ms=5))
        self.gate.write_text(point)

    def hung_pid(self, timeout=8):
        wait_for(lambda: self.flag.exists() and self.flag.read_text().strip(), timeout=timeout)
        return int(self.flag.read_text())

    def kill9(self, pid):
        os.kill(pid, signal.SIGKILL)
        wait_for(lambda: not pid_alive(pid))


class DaemonKill9(Kill9Case):
    def test_daemon_kill9_then_up_doorbell_still_works(self):
        """daemon 被 kill -9（上一任 cpu 可能還活著、握著 wake 的讀端）→ 再 aos up：起得來、帳本 ok、
        新 cpu 靠門鈴 10 秒內做完一件 --once（輪詢 30 秒）；上一任 cpu 不留下來。"""
        self.initialize({"default": {"count": 1}}, cpu=dict(POLL))
        self.up()
        self.wait_running("default", 1)
        old_cpu = self.kid_pid("default", 0)
        daemon = self.dstate()["pid"]
        os.kill(daemon, signal.SIGKILL)
        wait_for(lambda: not pid_alive(daemon))
        # 不斷言舊 cpu 還活著：控制 pipe 收到 EOF（daemon 死了）時，閒著的 cpu 照 spec/cpu/stop.md 會溫和地停，
        # 門鈴把控制 pipe 一起等，所以它可能馬上就停（全套測試負載下實際遇過）。手上有工作才會做完再停。

        again = self.up()                                                    # .daemon.lock 跟著 daemon 死掉就放了
        self.assertIn("新開", again.stdout)
        self.assertNotEqual(self.dstate()["pid"], daemon)
        self.integrity()
        wait_for(lambda: self.kid_pid("default", 0) not in (None, old_cpu), timeout=10)
        wait_for(lambda: not pid_alive(old_cpu), timeout=10)                  # 新 daemon 先收掉上一任才拉新的
        new_cpu = self.kid_pid("default", 0)
        cpu_home = self.cpu_home("default", 0)
        wait_for(lambda: (cpu_home / "wake").exists())
        self.assertEqual(read_json(cpu_home / "info.json")["poll_ms"], 30000)
        time.sleep(.5)                                                        # 讓新 cpu 進入 30 秒的睡

        target, runs = self.counter_job("one")
        started = time.monotonic()
        result = self.cli("add", self.home, target, "--name", "one", "--once", "--wait-ms", "20000", timeout=30)
        took = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(took, FAST, "門鈴沒叫醒新 cpu（等了 %.1f 秒）" % took)
        self.assertEqual(self.runs(runs), 1)
        self.assertEqual(self.kid_pid("default", 0), new_cpu)
        self.integrity()


class TickKill9(Kill9Case):
    def cpu_sleeps_long(self):
        self.assertEqual(read_json(self.cpu_home("default", 0) / "info.json")["poll_ms"], 30000)

    def boot_with_gate(self, point):
        self.initialize({"default": {"count": 1}}, cpu=dict(POLL))
        self.up()
        self.wait_running("default", 1)
        wait_for(lambda: (self.cpu_home("default", 0) / "wake").exists())
        self.cpu_sleeps_long()
        self.install_gate(point)
        time.sleep(.3)                                                        # 讓 cpu 進入 30 秒的睡

    def test_kill9_after_post_before_C(self):
        """第 8 步的單放了、門鈴按了，tick 在提交點 C 前被 kill -9：cpu 照樣醒來做完；
        下一格拿得到鎖、收回音、回給等的人；工作只跑一次。"""
        self.boot_with_gate("after-post")
        target, runs = self.counter_job("one")
        started = time.monotonic()
        name = aos_client.submit(self.home, "add", {"target": target, "name": "one", "once": True})
        pid = self.hung_pid()
        seq = self.state()["last_seq"]
        wait_for(lambda: self.runs(runs) == 1, timeout=FAST)                 # 卡住的 tick 按過的門鈴有用
        self.assertLess(time.monotonic() - started, FAST)
        self.kill9(pid)

        self.lock_free()
        response = aos_client.wait_response(self.home, name, timeout_ms=FAST * 1000, poll_ms=5)
        self.assertEqual(response.get("result", {}).get("code"), 0, response)
        self.assertLess(time.monotonic() - started, 2 * FAST)
        wait_for(lambda: self.state()["last_seq"] > seq)
        state = self.state()
        self.assertNotIn("one", state["procs"])                             # once 做完就拿掉
        self.assertEqual(state["busy"], {})
        time.sleep(.5)
        self.assertEqual(self.runs(runs), 1)                                 # 沒派兩次
        self.integrity()
        self.assertTrue(self.flag.exists())

    def test_kill9_after_D_before_post(self):
        """回音叫醒停著的 agent、提交點 D 記了派給誰，tick 在放單前被 kill -9：
        下一格靠 recent 補放、按門鈴，agent 10 秒內跑到（輪詢 30 秒），只多跑一次。"""
        self.boot_with_gate("none")                                          # 先不卡：停車那幾格要走完
        agent, agent_runs = self.counter_job("agent", code=102)
        self.add(agent, name="agent", interval_ms=3600000, park_ms=3600000)
        wait_for(lambda: self.runs(agent_runs) == 1, timeout=FAST)
        wait_for(lambda: (self.state()["procs"]["agent"].get("status"), self.state()["procs"]["agent"].get("parked"))
                 == ("queued", True), timeout=FAST)
        self.gate.write_text("after-D")

        q, q_runs = self.counter_job("q")
        started = time.monotonic()
        name = aos_client.submit(self.home, "add", {"target": q, "name": "q", "once": True, "wake": "agent"})
        pid = self.hung_pid(timeout=FAST)
        state = self.state()
        key = state["on"]["agent"]                                           # D 已存：記了派給誰
        req = state["busy"][key]["req"]
        self.assertEqual(state["procs"]["agent"]["status"], "running")
        self.assertFalse((self.cpu_home(*key.split("/")) / "requests" / req).exists())
        self.assertEqual(self.runs(agent_runs), 1)
        self.kill9(pid)

        self.lock_free()
        wait_for(lambda: self.runs(agent_runs) == 2, timeout=FAST)          # 下一格補放＋按門鈴
        self.assertLess(time.monotonic() - started, 2 * FAST)
        wait_for(lambda: self.state()["procs"]["agent"].get("parked") is True, timeout=FAST)
        response = aos_client.wait_response(self.home, name, timeout_ms=FAST * 1000, poll_ms=5)
        self.assertEqual(response.get("result", {}).get("code"), 0, response)
        time.sleep(.5)
        self.assertEqual((self.runs(q_runs), self.runs(agent_runs)), (1, 2))   # 沒派兩次、沒丟
        self.integrity()


if __name__ == "__main__":
    import unittest
    unittest.main()
