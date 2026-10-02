"""控制模組驗收（plan m3n-control-module.md 步驟 1～7）。真的開 bin/aos-daemon 與 bin/aos-ctl 子程序。

本檔：設定、主迴圈排程、環境（Step1Config、Step2Loop、Step4Env）。

都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。socket 放 self.d（/tmp 底下，路徑夠短）。
會留下來的任務照 test_daemon 的做法把 pid 寫進 `pids`，收尾時殺掉。
任務自己寫時間來量週期；daemon 那一行的時間只到秒。
任務寫的是 /proc/uptime（開機後的秒數，不會跳），不用 `date`：WSL 的牆上時鐘偶爾會被校時往前跳好幾秒
（實測 test_keep_schedule 約十次錯一次就是這個：daemon 的 monotonic 只過 0.96 秒，`date` 量到 3.3 秒；2026-10-01）。
"""
import os
import time
import unittest

from _util import PY
from _daemon_util import INHERIT, TICK, sh, tasks_json
from _ctl_util import CTL, CtlCase, STAMP, UPTIME


class Step1Config(CtlCase):

    def test_not_mounted(self):
        # modules 裡只有別的鍵：不建 socket、不傳兩個變數
        self.inst(sh('echo "${AOS_DAEMON_CTL_SOCKET-none} ${AOS_DAEMON_INST-none}" > env.txt'), "e.json")
        _, out, _ = self.start(self.config({"interval_ms": 10000, "modules": {"other": {}},
                                            "insts": {"e.json": {}}}))
        self.wait_for(lambda: self.results(out, "e.json"))
        self.assertEqual(self.read("env.txt").split(), ["none", "none"])
        self.assertEqual(sorted(os.listdir(self.d)), ["config.json", "config.json.lock", "e.json", "env.txt"])

    def test_socket_relative_to_start(self):
        self.inst({"argv": ["true"]}, "sub/x.json")
        self.start(self.config({"cwd": "sub", "interval_ms": 10000,
                                "modules": {"control": {"socket": "./s", "other": 1}},
                                "insts": {"x.json": {}}}))
        self.wait_for(lambda: self.is_sock("sub/s"))
        self.assertEqual(self.send({"status": "x.json"}, os.path.join(self.d, "sub/s"))["inst"], "x.json")

    def test_no_socket_key(self):
        r = self.run_cfg(self.config({"interval_ms": 5, "insts": {}, "modules": {"control": {}}}))
        self.assertEqual(r.returncode, 1)


class Step2Loop(CtlCase):

    def test_wake_restarts_period(self):
        self.inst(sh(STAMP), "r.json")
        self.up({"r.json": {}}, 1500)
        self.wait_for(lambda: len(self.runs()) == 1)
        time.sleep(0.3)
        self.assertEqual(self.send({"wake": "r.json"}), {"ok": True})
        self.wait_for(lambda: len(self.runs()) == 2, timeout=1)
        self.wait_for(lambda: len(self.runs()) == 3, timeout=4)
        t1, t2, t3 = self.runs()[:3]
        self.assertGreaterEqual(t3 - t2, 1.45)              # 週期從叫醒那次結束重新算

    def test_keep_schedule(self):
        # 第一次結束（e1）後 due＝e1＋1.5；叫醒那次（帶 keep_schedule）不碰 due，所以第三次在 e1＋1.5 跑。
        # 要是被重算，第三次會在叫醒那次結束（晚於 t2）＋1.5 之後，t3－t2 一定 ≥ 1.5；所以判準就是「t3－t2 < 1.5」。
        # 等第一次真的跑完（status 有 last_end、不在跑）再睡 0.5 秒才叫醒，不靠第一次收尾多快，留 0.5 秒的餘裕。
        self.inst(sh(STAMP), "r.json")
        self.up({"r.json": {}}, 1500)
        self.wait_for(lambda: len(self.runs()) == 1)
        self.wait_for(lambda: (lambda st: st["last_end"] is not None and not st["running"])(
            self.send({"status": "r.json"})))
        time.sleep(0.5)
        self.assertEqual(self.send({"wake": "r.json", "keep_schedule": True}), {"ok": True})
        self.wait_for(lambda: len(self.runs()) == 2, timeout=1)
        self.wait_for(lambda: len(self.runs()) == 3, timeout=4)
        t1, t2, t3 = self.runs()[:3]
        self.assertLess(t3 - t2, 1.5)                       # 原本那次照跑，不是從第二次重算
        self.assertGreaterEqual(t3 - t1, 1.45)

    def busy(self, wake):
        self.inst(sh("echo s >> log; sleep 0.5; echo e >> log"), "s.json")
        _, out, _ = self.up({"s.json": {}}, 10000)
        self.wait_for(lambda: self.exists("log"))
        for _ in range(5):
            self.assertEqual(self.send(wake), {"ok": True})
        self.assertEqual(self.send({"status": "s.json"})["pending"], not wake.get("skip_while_running"))
        time.sleep(1.8)
        return self.read("log").split(), out

    def test_wake_while_running_once(self):
        log, out = self.busy({"wake": "s.json"})
        self.assertEqual(log, ["s", "e", "s", "e"])         # 剛好補一次，不疊著跑

    def test_skip_while_running(self):
        log, out = self.busy({"wake": "s.json", "skip_while_running": True})
        self.assertEqual(log, ["s", "e"])

    def test_keep_schedule_overrun(self):
        # 叫醒那次跑太久、蓋過原本的時刻：結束後不馬上又跑，due 從這次結束重算
        self.inst(sh("%s >> starts; sleep 0.8; %s >> ends" % (UPTIME, UPTIME)), "k.json")
        self.up({"k.json": {}}, 300)
        self.wait_for(lambda: len(self.runs("ends")) == 1)
        self.assertEqual(self.send({"wake": "k.json", "keep_schedule": True}), {"ok": True})
        self.wait_for(lambda: len(self.runs("starts")) == 3, timeout=4)
        self.assertGreaterEqual(self.runs("starts")[2] - self.runs("ends")[1], 0.29)

    def test_pause_resume(self):
        self.inst(sh(STAMP), "r.json")
        _, out, _ = self.up({"r.json": {}}, 100)
        self.wait_for(lambda: len(self.runs()) >= 2)
        self.assertEqual(self.send({"pause": "r.json"}), {"ok": True})
        self.assertEqual(self.send({"pause": "r.json"}), {"ok": True})   # 已暫停再 pause 也成功
        self.wait_for(lambda: self.has(out, "inst=r.json paused"))
        time.sleep(0.4)                                     # 正在跑的那次照樣跑完
        n = len(self.runs())
        time.sleep(1)
        self.assertEqual(len(self.runs()), n)
        st = self.send({"status": "r.json"})
        self.assertEqual((st["paused"], st["next"], st["last_exit"]), (True, None, 0))
        self.assertEqual(self.send({"resume": "r.json"}), {"ok": True})
        self.wait_for(lambda: self.has(out, "inst=r.json resumed"))
        self.wait_for(lambda: len(self.runs()) >= n + 3, timeout=3)

    def test_wake_while_paused(self):
        # 待問 1 照建議：暫停中 wake 跑一次，跑完照樣暫停
        self.inst(sh(STAMP), "r.json")
        self.up({"r.json": {}}, 100)
        self.wait_for(lambda: len(self.runs()) >= 1)
        self.send({"pause": "r.json"})
        time.sleep(0.4)
        n = len(self.runs())
        self.assertEqual(self.send({"wake": "r.json"}), {"ok": True})
        self.wait_for(lambda: len(self.runs()) == n + 1, timeout=1)
        time.sleep(0.8)
        self.assertEqual(len(self.runs()), n + 1)
        self.assertTrue(self.send({"status": "r.json"})["paused"])

    def test_stopped(self):
        self.inst(sh(STAMP + "; exit 1"), "f.json")
        _, out, _ = self.up({"f.json": {"stop_on_nonzero": True}}, 50)
        self.wait_for(lambda: self.has(out, "inst=f.json stopped"))
        self.assertEqual(self.send({"wake": "f.json"}),
                         {"ok": False, "error": "stopped", "detail": "f.json"})
        st = self.send({"status": "f.json"})
        self.assertEqual((st["stopped"], st["last_exit"], st["next"]), (True, 1, None))
        time.sleep(0.4)
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual(self.send({"resume": "f.json"}), {"ok": True})   # resume 救回、跑一次、又停
        self.wait_for(lambda: sum(1 for l in list(out) if l.endswith(" stopped")) == 2)
        time.sleep(0.4)
        self.assertEqual(self.results(out, "f.json"), [1, 1])


class Step4Env(CtlCase):

    def test_env_values(self):
        self.inst(sh('echo "$AOS_DAEMON_CTL_SOCKET" > env.txt; echo "$AOS_DAEMON_INST" >> env.txt'),
                  "jobs/report.json")
        self.up({"jobs/report.json": {}}, 10000)
        self.wait_for(lambda: self.exists("jobs/env.txt") and len(self.read("jobs/env.txt").split()) == 2)
        self.assertEqual(self.read("jobs/env.txt").split(), [self.sock, "jobs/report.json"])

    def test_through_nodes(self):
        # 頂層 a 的 inst 跑 aos-tick；a 的任務一項寫檔、一項跑 aos-tick b；b 的任務寫檔，
        # 第一次還順便 aos-ctl wake（不帶 inst）：叫醒的是頂層 a
        dump = 'echo "$AOS_DAEMON_INST" > "$AOS_TICK_CWD/%s"'
        self.inst({"argv": [TICK], "stderr": INHERIT}, "a/inst.json")
        self.write("a/.aos/tasks.json", tasks_json(
            {"id": "w", "argv": ["sh", "-c", dump % "env.txt"]},
            {"id": "b", "argv": [TICK, os.path.join(self.d, "a", "b")]}))
        self.write("a/b/.aos/tasks.json", tasks_json(
            {"id": "w", "argv": ["sh", "-c", (dump % "env.txt") + "; " + STAMP +
                                 "; [ -e woke ] || { touch woke; %s %s wake; }" % (PY, CTL)]}))
        _, out, _ = self.up({"a": {}}, 10000)
        self.wait_for(lambda: len(self.results(out, "a")) >= 2)
        self.assertEqual(self.results(out, "a"), [0, 0])
        for rel in ("a/env.txt", "a/b/env.txt"):
            self.assertEqual(self.read(rel).strip(), "a")
        self.assertEqual(len(self.runs("a/b/runs")), 2)


if __name__ == "__main__":
    unittest.main()
