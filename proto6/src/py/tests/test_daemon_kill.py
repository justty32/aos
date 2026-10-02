"""第十九批驗收（verdicts 11「2026-10-01 第十九批」）：daemon 跑 daemon 用到的三件事。真的開 bin/aos-daemon。

- `OutputCap`：每次、每條最多留 exec_output_max_bytes，丟最早的，標頭 `dropped=`。
- `ConfigLock`：同一份設定開第二個 daemon，拿不到鎖：stderr 一行、回 1。
- `Kill`：控制模組的 kill／restart（先 TERM，寬限後 KILL）。
- `KillSeq`：kill_run() 只對同一次送訊號（舊的請求不殺到下一次）。
- `KillCgroup`：掛 cgroup 時 KILL 那一步清整個框（拿不到委派的 scope 就跳過）。
- `KillOtherAccount`：帳號模組底下 kill 別的帳號的項（經 root 端送；拿不到 namespace 假 root 就跳過）。
"""
import os
import re
import time
import unittest

from _ctl_util import CtlCase
from _daemon_util import TS, DaemonCase, INHERIT, sh

import aos_daemon

LOUD = {"stdout": INHERIT, "stderr": INHERIT}
# 印 0000|0001|…0299|（每筆 5 bytes，共 1500 bytes）到 stdout，stderr 印同樣的東西
NUMBERS = 'i=0; while [ $i -lt 300 ]; do printf "%04d|" $i; i=$((i+1)); done'


class OutputCap(DaemonCase):

    def blocks(self, rel):
        """寫出的檔切成 [(標頭, 內容)]。"""
        text = self.read(rel)
        parts = re.split(r"^(== .* ==)\n", text, flags=re.M)
        return [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]

    def test_drops_oldest_both_streams(self):
        self.inst(sh(NUMBERS + "; " + NUMBERS + " >&2", **LOUD), "x.json")
        _, out, _ = self.start(self.config({"interval_ms": 100000, "exec_out_path": "out.log",
                                            "exec_err_path": "err.log", "exec_output_max_bytes": 50,
                                            "insts": {"x.json": {}}}))
        self.wait_for(lambda: self.results(out, "x.json") == [0])
        want = "".join("%04d|" % i for i in range(290, 300)) + "\n"     # 最後 50 bytes，補一個換行
        for rel, stream in (("out.log", "stdout"), ("err.log", "stderr")):
            [(head, body)] = self.blocks(rel)
            self.assertRegex(head, r"^== %s %s index=0 inst=x\.json dropped=1450 ==$" % (TS, stream))
            self.assertEqual(body, want)

    def test_shared_cap_item_key_ignored(self):
        # 上限只有頂層一個、各項共用；寫在某項裡照不認得的鍵忽略（使用者第十九批）
        self.inst(sh(NUMBERS, **LOUD), "a/inst.json")
        self.inst(sh(NUMBERS, **LOUD), "b/inst.json")
        _, out, _ = self.start(self.config({"interval_ms": 100000, "exec_out_path": "<inst>/out.log",
                                            "exec_output_max_bytes": 10,
                                            "insts": {"a/inst.json": {},
                                                      "b/inst.json": {"exec_output_max_bytes": 1500}}}))
        self.wait_for(lambda: self.results(out, "a/inst.json") == [0] and self.results(out, "b/inst.json") == [0])
        for rel in ("a/out.log", "b/out.log"):
            [(head, body)] = self.blocks(rel)
            self.assertTrue(head.endswith(" dropped=1490 =="), head)
            self.assertEqual(body, "0298|0299|\n")

    def test_exact_cap_no_drop(self):
        self.inst(sh(NUMBERS, **LOUD), "x.json")
        _, out, _ = self.start(self.config({"interval_ms": 100000, "exec_out_path": "out.log",
                                            "exec_output_max_bytes": 1500, "insts": {"x.json": {}}}))
        self.wait_for(lambda: self.results(out, "x.json") == [0])
        [(head, body)] = self.blocks("out.log")
        self.assertNotIn("dropped", head)               # 剛好等於上限：不丟、不加
        self.assertEqual(len(body), 1501)

    def test_endless_output_bounded(self):
        # 一直印 20 MB：只留最後 1000 bytes
        self.inst(sh("yes abcdefghi | head -c 20000000", **LOUD), "y.json")
        _, out, _ = self.start(self.config({"interval_ms": 100000, "exec_out_path": "out.log",
                                            "exec_output_max_bytes": 1000, "insts": {"y.json": {}}}))
        self.wait_for(lambda: self.results(out, "y.json") == [0], timeout=20)
        [(head, body)] = self.blocks("out.log")
        self.assertTrue(head.endswith(" dropped=19999000 =="))
        self.assertEqual(len(body), 1000)

    def test_zero_keeps_header_only(self):
        self.inst(sh("echo hi", **LOUD), "z.json")
        _, out, _ = self.start(self.config({"interval_ms": 100000, "exec_out_path": "out.log",
                                            "exec_output_max_bytes": 0, "insts": {"z.json": {}}}))
        self.wait_for(lambda: self.results(out, "z.json") == [0])
        [(head, body)] = self.blocks("out.log")
        self.assertTrue(head.endswith(" dropped=3 =="))
        self.assertEqual(body, "\n")

    def test_bad_value(self):
        for v in (-1, "1", True, 1.5):
            r = self.run_cfg(self.config({"interval_ms": 5, "exec_output_max_bytes": v, "insts": {"x": {}}}))
            self.assertEqual(r.returncode, 1, v)
            self.assertEqual(r.stderr, "aos-daemon: config: exec_output_max_bytes 要是非負整數\n")
        r = self.run_cfg(self.config({"interval_ms": 5, "lock_path": "", "insts": {}}))
        self.assertEqual(r.stderr, "aos-daemon: config: lock_path 要是非空字串\n")


class ConfigLock(DaemonCase):

    def test_second_daemon_exits_1(self):
        # 拿不到鎖：stderr 一行、回 1，沒開 socket（使用者第十九批：「拿不到鎖就報錯退出」）
        self.inst(sh("echo x >> runs"), "x.json")
        cfg = self.config({"interval_ms": 200, "modules": {"control": {"socket": "./aos.sock"}},
                           "insts": {"x.json": {}}})
        _, out1, _ = self.start(cfg)
        self.wait_for(lambda: self.results(out1, "x.json"))
        ino = os.stat(os.path.join(self.d, "aos.sock")).st_ino
        r = self.run_cfg(cfg)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr, "aos-daemon: lock: another aos-daemon holds %s\n" % (cfg + ".lock"))
        self.assertEqual(r.stdout, "")
        self.assertEqual(os.stat(os.path.join(self.d, "aos.sock")).st_ino, ino)   # 第一個的 socket 沒被搶
        n = len(self.results(out1, "x.json"))
        self.wait_for(lambda: len(self.results(out1, "x.json")) > n)               # 第一個照跑

    def test_free_after_first_exits(self):
        self.inst(sh("true"), "x.json")
        cfg = self.config({"interval_ms": 100000, "insts": {"x.json": {}}})
        p, out1, _ = self.start(cfg)
        self.wait_for(lambda: self.results(out1, "x.json"))
        p.terminate()
        p.wait()
        _, out2, _ = self.start(cfg)
        self.wait_for(lambda: self.results(out2, "x.json"))

    def test_lock_path_relative_to_config(self):
        self.inst(sh("true"), "x.json")
        os.makedirs(os.path.join(self.d, "conf"))
        cfg = self.config({"cwd": ".", "interval_ms": 100000, "lock_path": "my.lock", "insts": {"x.json": {}}},
                          "conf/d.json")
        _, out, _ = self.start(cfg)
        self.wait_for(lambda: self.results(out, "x.json"))
        self.assertTrue(self.exists("conf/my.lock"))
        self.assertFalse(self.exists("conf/d.json.lock"))


# 任務收到 TERM 就記一筆、以 7 結束；不然睡很久
POLITE = "trap 'echo term >> log; exit 7' TERM; echo start >> log; sleep 1000 & wait"
# 不理 TERM（連子程序也不理）
STUBBORN = "trap '' TERM; echo start >> log; echo $$ >> pids; sleep 1000"


class Kill(CtlCase):

    def up_kill(self, insts, interval_ms=100000, grace_ms=300, **top):
        cfg = self.config(dict({"interval_ms": interval_ms,
                                "modules": {"control": {"socket": "./aos.sock", "kill_grace_ms": grace_ms}},
                                "insts": insts}, **top))
        p, out, err = self.start(cfg)
        self.wait_for(lambda: self.exists("aos.sock"))
        return p, out, err

    def lines(self, rel="log"):
        return self.read(rel).split() if self.exists(rel) else []

    def test_term_lets_task_finish(self):
        self.inst(sh(POLITE), "p.json")
        _, out, _ = self.up_kill({"p.json": {}})
        self.wait_for(lambda: self.lines() == ["start"])
        t0 = time.monotonic()
        self.assertEqual(self.send({"kill": "p.json"}), {"ok": True})
        self.wait_for(lambda: self.results(out, "p.json") == [7], timeout=3)
        self.assertLess(time.monotonic() - t0, 2)
        self.assertEqual(self.lines(), ["start", "term"])
        time.sleep(0.5)
        self.assertEqual(self.results(out, "p.json"), [7])          # 照週期排下一次（很久以後）
        self.assertFalse(self.send({"status": "p.json"})["running"])

    def test_kill_after_grace(self):
        self.inst(sh(STUBBORN), "s.json")
        _, out, _ = self.up_kill({"s.json": {}}, grace_ms=400)
        self.wait_for(lambda: self.lines() == ["start"])
        task = int(self.read("pids").split()[0])
        t0 = time.monotonic()
        self.assertEqual(self.ctl("kill", "s.json").returncode, 0)
        self.wait_for(lambda: self.results(out, "s.json") == [137], timeout=5)
        self.assertGreaterEqual(time.monotonic() - t0, 0.35)
        self.wait_for(lambda: not os.path.exists("/proc/%d" % task) or self._zombie(task))

    @staticmethod
    def _zombie(pid):
        try:
            with open("/proc/%d/stat" % pid) as f:
                return f.read().rsplit(")", 1)[1].split()[0] == "Z"
        except FileNotFoundError:
            return True

    def test_not_running_is_noop(self):
        self.inst(sh("true"), "t.json")
        _, out, _ = self.up_kill({"t.json": {}})
        self.wait_for(lambda: self.results(out, "t.json") == [0])
        self.assertEqual(self.send({"kill": "t.json"}), {"ok": True})
        time.sleep(0.4)
        self.assertEqual(self.results(out, "t.json"), [0])
        self.assertEqual(self.send({"kill": "nope"})["error"], "unknown_inst")

    def test_restart_runs_again_now(self):
        self.inst(sh(POLITE), "p.json")
        _, out, _ = self.up_kill({"p.json": {"stop_on_nonzero": True}})
        self.wait_for(lambda: self.lines() == ["start"])
        self.assertEqual(self.ctl("restart", "p.json").returncode, 0)
        self.wait_for(lambda: self.lines() == ["start", "term", "start"], timeout=3)
        self.assertEqual(self.results(out, "p.json"), [7])
        self.assertFalse(any(l.endswith("inst=p.json stopped") for l in out))   # restart 殺的那次不算
        self.assertTrue(self.send({"status": "p.json"})["running"])

    def test_restart_not_running_is_wake(self):
        self.inst(sh("echo x >> log"), "t.json")
        _, out, _ = self.up_kill({"t.json": {}})
        self.wait_for(lambda: self.results(out, "t.json") == [0])
        self.assertEqual(self.send({"restart": "t.json"}), {"ok": True})
        self.wait_for(lambda: self.results(out, "t.json") == [0, 0], timeout=2)

    def test_kill_counts_for_stop_on_nonzero(self):
        self.inst(sh(POLITE), "p.json")
        _, out, _ = self.up_kill({"p.json": {"stop_on_nonzero": True}})
        self.wait_for(lambda: self.lines() == ["start"])
        self.send({"kill": "p.json"})
        self.wait_for(lambda: any(l.endswith("inst=p.json stopped") for l in out), timeout=3)
        self.assertEqual(self.send({"restart": "p.json"})["error"], "stopped")

    def test_bad_grace(self):
        for v in (-1, "5", True):
            r = self.run_cfg(self.config({"interval_ms": 5, "insts": {},
                                          "modules": {"control": {"socket": "./s", "kill_grace_ms": v}}}))
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stderr, "aos-daemon: config: modules.control.kill_grace_ms 要是非負數\n")

    def test_kills_whole_tree(self):
        # 任務底下再開一個 setsid 的孫子（還在親子樹裡）：TERM 那一步也送到
        self.inst(sh("trap 'exit 0' TERM; setsid sh -c 'trap \"echo grand >> log; exit 0\" TERM; "
                     "echo $$ >> pids; sleep 1000 & wait' & echo start >> log; sleep 1000 & wait"), "t.json")
        _, out, _ = self.up_kill({"t.json": {}})
        self.wait_for(lambda: self.exists("pids") and "start" in self.lines())
        self.send({"kill": "t.json"})
        self.wait_for(lambda: "grand" in self.lines(), timeout=3)
        self.wait_for(lambda: self.results(out, "t.json") == [0], timeout=3)


try:
    from _cgroup_util import CgCase, procs
except ImportError:                  # pragma: no cover
    CgCase = None


if CgCase is not None:
    class KillCgroup(CgCase):

        def test_kill_clears_frame(self):
            # 不理 TERM 的任務另外留一個跳出親子樹的背景程序：KILL 那一步 cgroup.kill 整個框
            self.inst(sh("trap '' TERM; (setsid sh -c 'trap \"\" TERM; sleep 1000' &); echo start >> log; "
                         "sleep 1000"), "c.json")
            cfg = self.config({"interval_ms": 100000,
                               "modules": {"cgroup": {}, "control": {"socket": "./aos.sock", "kill_grace_ms": 300}},
                               "insts": {"c.json": {}}})
            _, out, _ = self.start(cfg)
            self.wait_for(lambda: self.exists("aos.sock") and self.exists("log"), timeout=10)
            self.send_ctl({"kill": "c.json"})
            self.wait_for(lambda: self.results(out, "c.json") == [137], timeout=8)
            self.assertEqual(procs(self.frame("c.json")), [])

        def send_ctl(self, obj):
            import json
            import socket
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(os.path.join(self.d, "aos.sock"))
                s.sendall((json.dumps(obj) + "\n").encode())
                return json.loads(s.makefile("rb").readline())


from _account_util import NS_OK, NsCase, OTHER  # noqa: E402


class KillSeq(unittest.TestCase):
    """kill_run() 每次送訊號前在 cond 底下核序號：那一次已經結束、下一次已經開了就不送（不殺錯）。"""

    def test_only_same_run(self):
        import aos_daemon_kill
        sent = []
        orig = aos_daemon_kill.signal_run
        aos_daemon_kill.signal_run = lambda item, final: sent.append(final)
        self.addCleanup(setattr, aos_daemon_kill, "signal_run", orig)
        item = aos_daemon.Item(0, "a", 1000, False, None)
        item.running, item.run_seq = True, 2
        aos_daemon_kill.kill_run(item, 1, 0)        # 第 1 次已經結束、第 2 次在跑：一個都不送
        self.assertEqual(sent, [])
        aos_daemon_kill.kill_run(item, 2, 0)        # 同一次、寬限 0：TERM 再 KILL
        self.assertEqual(sent, [False, True])
        item.running = False
        aos_daemon_kill.kill_run(item, 2, 0)        # 已經沒在跑
        self.assertEqual(sent, [False, True])


class KillOtherAccount(NsCase):

    def test_kill_other_user_via_root(self):
        self.inst(sh(STUBBORN), "b.json")
        self.inst(sh(POLITE.replace(">> log", ">> plog")), "c.json")
        cfg = self.cfg({"b.json": {"account": {"user": OTHER}}, "c.json": {"account": {"user": OTHER}}},
                       control={"socket": "./aos.sock", "kill_grace_ms": 300})
        _, out, _ = self.start_ns(cfg)
        self.wait_for(lambda: self.exists("aos.sock") and self.exists("log") and self.exists("plog"), timeout=8)
        import json
        import socket

        def send(obj):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(os.path.join(self.d, "aos.sock"))
                s.sendall((json.dumps(obj) + "\n").encode())
                return json.loads(s.makefile("rb").readline())
        self.assertEqual(send({"kill": "c.json"}), {"ok": True})
        self.wait_for(lambda: self.results(out, "c.json") == [7], timeout=5)
        self.assertEqual(self.read("plog").split(), ["start", "term"])
        self.assertEqual(send({"kill": "b.json"}), {"ok": True})
        self.wait_for(lambda: self.results(out, "b.json") == [137], timeout=5)


if __name__ == "__main__":
    unittest.main()
