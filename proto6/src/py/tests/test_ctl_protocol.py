"""控制模組驗收（plan m3n-control-module.md 步驟 1～7）。真的開 bin/aos-daemon 與 bin/aos-ctl 子程序。

本檔：協議、aos-ctl 命令列、socket 檔（Step3Protocol、Step5Ctl、Step6SocketFile）。

都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。socket 放 self.d（/tmp 底下，路徑夠短）。
會留下來的任務照 test_daemon 的做法把 pid 寫進 `pids`，收尾時殺掉。
任務自己寫時間來量週期；daemon 那一行的時間只到秒。
任務寫的是 /proc/uptime（開機後的秒數，不會跳），不用 `date`：WSL 的牆上時鐘偶爾會被校時往前跳好幾秒
（實測 test_keep_schedule 約十次錯一次就是這個：daemon 的 monotonic 只過 0.96 秒，`date` 量到 3.3 秒；2026-10-01）。
"""
import json
import os
import signal
import socket
import time
import unittest

from _util import PY
from _daemon_util import TS, sh
from _ctl_util import CONTROL, CTL, CtlCase, STAMP


class Step3Protocol(CtlCase):

    def test_wake_direct(self):
        self.inst(sh(STAMP), "r.json")
        self.up({"r.json": {}}, 10000)
        self.wait_for(lambda: len(self.runs()) == 1)
        self.assertEqual(self.send({"wake": "r.json"}), {"ok": True})
        self.wait_for(lambda: len(self.runs()) == 2, timeout=1)

    def test_status(self):
        self.inst(sh("touch began; sleep 0.5"), "s.json")
        self.up({"s.json": {}}, 10000)
        self.wait_for(lambda: self.exists("began"))
        self.assertEqual(self.send({"status": "s.json"}),
                         {"ok": True, "inst": "s.json", "running": True, "pending": False,
                          "paused": False, "stopped": False, "last_exit": None,
                          "last_end": None, "next": None})
        self.wait_for(lambda: self.send({"status": "s.json"})["last_exit"] == 0)
        st = self.send({"status": "s.json"})
        self.assertFalse(st["running"])
        self.assertRegex(st["last_end"], "^%s$" % TS)
        self.assertRegex(st["next"], "^%s$" % TS)
        self.assertGreater(st["next"], st["last_end"])

    def test_errors(self):
        self.inst({"argv": ["true"]}, "a.json")
        self.up({"a.json": {}}, 10000)
        self.assertEqual(self.send({"wake": "b.json"}),
                         {"ok": False, "error": "unknown_inst", "detail": "b.json"})
        for bad in ({"nuke": "a.json"}, {"wake": "a.json", "pause": "a.json"}, {"status": None},
                    {"wake": "a.json", "keep_schedule": "yes"}, [1], b"hello\n", b"{\"wake\":\"a.json\"}"):
            r = self.send(bad)
            self.assertEqual((r["ok"], r["error"]), (False, "bad_request"), bad)
        # pause 帶 wake 的選項、多帶別的鍵：忽略
        self.assertEqual(self.send({"pause": "a.json", "keep_schedule": "x", "who": 1}), {"ok": True})
        self.assertEqual(self.send({"resume": "a.json"}), {"ok": True})
        # 看不懂的欄位照收不理（使用者 2026-10-01）：wake、status 也一樣
        self.assertEqual(self.send({"wake": "a.json", "why": {"x": [1]}}), {"ok": True})
        self.assertEqual(self.send({"status": "a.json", "verbose": True})["inst"], "a.json")

    def test_silent_client(self):
        self.inst({"argv": ["true"]}, "a.json")
        self.up({"a.json": {}}, 10000)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as quiet:
            quiet.connect(self.sock)
            t0 = time.monotonic()
            self.assertEqual(self.send({"status": "a.json"})["inst"], "a.json")   # 最多晚約 1 秒
            self.assertLess(time.monotonic() - t0, 1.5)
            quiet.settimeout(3)
            self.assertEqual(quiet.recv(10), b"")                              # 被關掉、不回
            self.assertLess(time.monotonic() - t0, 1.5)


class Step5Ctl(CtlCase):

    def test_wake_self_in_task(self):
        # 任務裡 aos-ctl wake（不帶 inst）：回 0，自己這一項跑完立刻補一次
        self.inst(sh(STAMP + "; [ -e woke ] || { touch woke; %s %s wake; echo $? > rc; }" % (PY, CTL)), "r.json")
        self.up({"r.json": {}}, 10000)
        self.wait_for(lambda: len(self.runs()) == 2, timeout=3)
        self.assertEqual(self.read("rc").strip(), "0")

    def test_skip_in_task(self):
        self.inst(sh(STAMP + "; %s %s wake --skip-while-running; echo $? >> rc" % (PY, CTL)), "r.json")
        self.up({"r.json": {}}, 10000)
        self.wait_for(lambda: self.exists("rc"))
        time.sleep(0.8)
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual(self.read("rc").split(), ["0"])

    def test_pause_in_task(self):
        self.inst(sh(STAMP + "; %s %s pause; echo $? >> rc" % (PY, CTL)), "r.json")
        self.up({"r.json": {}}, 100)
        self.wait_for(lambda: self.exists("rc"))
        time.sleep(0.8)
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual(self.read("rc").split(), ["0"])

    def test_status_in_task(self):
        self.inst(sh("%s %s status > st.json" % (PY, CTL)), "jobs/x.json")
        self.up({"jobs/x.json": {}}, 10000)
        self.wait_for(lambda: self.exists("jobs/st.json") and self.read("jobs/st.json"))
        st = json.loads(self.read("jobs/st.json"))
        self.assertEqual((st["inst"], st["running"]), ("jobs/x.json", True))

    def test_errors(self):
        self.inst({"argv": ["true"]}, "a.json")
        self.up({"a.json": {}}, 10000)
        r = self.ctl("status", "a.json")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["inst"], "a.json")
        self.assertEqual(r.stdout.count("\n"), 1)
        r = self.ctl("wake", AOS_DAEMON_INST="a.json")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        for args, env, code in ((["wake", "b.json"], {}, "unknown_inst"),
                                (["status", "a.json"], {"AOS_DAEMON_CTL_SOCKET": None}, "no_daemon"),
                                (["status"], {"AOS_DAEMON_INST": None}, "no_inst"),
                                (["status", "a.json"], {"AOS_DAEMON_CTL_SOCKET": os.path.join(self.d, "nope")},
                                 "connect"),
                                (["nuke", "a.json"], {}, "usage"),
                                ([], {}, "usage"),
                                (["status", "a.json", "b"], {}, "usage"),
                                (["pause", "--keep-schedule", "a.json"], {}, "usage")):
            r = self.ctl(*args, **env)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith(code + ": "), (args, r.stderr))
            self.assertEqual(r.stderr.count("\n"), 1, r.stderr)


class Step6SocketFile(CtlCase):

    def check(self, sig):
        self.inst({"argv": ["true"]}, "a.json")
        p, _, _ = self.up({"a.json": {}}, 10000)
        os.kill(p.pid, sig)
        self.assertEqual(p.wait(timeout=1), 0)
        self.assertFalse(self.exists("aos.sock"))

    def test_sigint(self):
        self.check(signal.SIGINT)

    def test_sigterm(self):
        self.check(signal.SIGTERM)

    def test_stale_file(self):
        self.write("aos.sock", "上次留下的")
        self.inst(sh(STAMP), "r.json")
        cfg = self.config({"interval_ms": 10000, "modules": CONTROL, "insts": {"r.json": {}}})
        self.start(cfg)
        self.wait_for(self.is_sock)
        self.wait_for(lambda: len(self.runs()) == 1)
        self.assertEqual(self.send({"wake": "r.json"}), {"ok": True})
        self.wait_for(lambda: len(self.runs()) == 2)


if __name__ == "__main__":
    unittest.main()
