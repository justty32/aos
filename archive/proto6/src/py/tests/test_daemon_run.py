"""aos-daemon 第三段驗收（plan m3-daemon-core.md）。真的開 bin/aos-daemon 子程序。

本檔：週期、停止、信號、node 當模組（Step3Period～Step6Tick）。

都用暫存資料夾、短週期、假 inst；不要 root、systemd、網路。
daemon 不殺子程序（步驟 5），所以會留下來的任務一律把自己的 pid 寫進 `pids`，測試收尾時連同
它的 process group 一起殺掉（任務被 aos-exec 開在自己的 session，pid 就是 group id）。
"""
import json
import os
import signal
import time
import unittest

from _daemon_util import DaemonCase, INHERIT, LINE, TICK, sh, tasks_json


class Step3Period(DaemonCase):

    def test_first_run_and_repeat(self):
        self.inst(sh("echo x >> runs"), "r.json")
        _, out, _ = self.start(self.config({"interval_ms": 100, "insts": {"r.json": {}}}))
        self.wait_for(lambda: self.exists("runs"), timeout=2)
        self.wait_for(lambda: len(self.results(out, "r.json")) >= 4, timeout=3)

    def test_no_overlap(self):
        self.inst(sh("echo start >> log; sleep 0.3; echo end >> log"), "s.json")
        _, out, _ = self.start(self.config({"interval_ms": 50, "insts": {"s.json": {}}}))
        self.wait_for(lambda: len(self.results(out, "s.json")) >= 3)
        log = self.read("log").split()
        self.assertEqual(log[:6], ["start", "end"] * 3)
        ms = [int(LINE.match(l).group(4)) for l in list(out) if LINE.match(l)]
        self.assertTrue(all(m >= 300 for m in ms), ms)

    def test_stuck_does_not_block_others(self):
        self.inst(sh("echo $$ >> pids; exec sleep 30"), "stuck.json")
        self.inst({"argv": ["true"]}, "ok.json")
        cfg = self.config({"interval_ms": 50, "insts": {"stuck.json": {}, "ok.json": {}}})
        _, out, _ = self.start(cfg)
        self.wait_for(lambda: len(self.results(out, "ok.json")) >= 4)
        self.assertEqual(self.results(out, "stuck.json"), [])


class Step4Stop(DaemonCase):

    def test_stop(self):
        self.inst({"argv": ["false"]}, "f.json")
        self.inst({"argv": ["true"]}, "ok.json")
        cfg = self.config({"interval_ms": 50, "insts": {
            "f.json": {"stop_on_nonzero": True}, "ok.json": {}}})
        p, out, _ = self.start(cfg)
        self.wait_for(lambda: any(l.endswith(" inst=f.json stopped") for l in list(out)))
        n_ok = len(self.results(out, "ok.json"))
        time.sleep(0.6)
        self.assertEqual(self.results(out, "f.json"), [1])
        self.assertEqual(sum(1 for l in list(out) if l.endswith("stopped")), 1)
        self.assertGreater(len(self.results(out, "ok.json")), n_ok)
        self.assertIsNone(p.poll())

    def test_all_stopped_stays_open(self):
        p, out, _ = self.start(self.config({"interval_ms": 50, "stop_on_nonzero": True,
                                            "insts": {"nope": {}}}))
        self.wait_for(lambda: any(l.endswith("stopped") for l in list(out)))
        self.assertEqual(self.results(out, "nope"), [1])     # 目標不存在：aos-exec 用法錯 1
        time.sleep(0.4)
        self.assertIsNone(p.poll())                         # 全停了 daemon 照樣開著

    def test_no_stop(self):
        self.inst({"argv": ["false"]}, "f.json")
        _, out, _ = self.start(self.config({"interval_ms": 50, "insts": {"f.json": {}}}))
        self.wait_for(lambda: len(self.results(out, "f.json")) >= 3)
        self.assertEqual(set(self.results(out, "f.json")), {1})
        self.assertFalse(any(l.endswith("stopped") for l in list(out)))

    def test_zero_never_stops(self):
        self.inst({"argv": ["true"]}, "t.json")
        _, out, _ = self.start(self.config({"interval_ms": 50, "stop_on_nonzero": True,
                                            "insts": {"t.json": {}}}))
        self.wait_for(lambda: len(self.results(out, "t.json")) >= 3)
        self.assertFalse(any(l.endswith("stopped") for l in list(out)))


class Step5Signals(DaemonCase):

    def check(self, sig):
        self.inst({"argv": ["true"]}, "t.json")
        p, out, _ = self.start(self.config({"interval_ms": 50, "insts": {"t.json": {}}}))
        self.wait_for(lambda: out)
        os.kill(p.pid, sig)
        self.assertEqual(p.wait(timeout=1), 0)

    def test_sigint(self):
        self.check(signal.SIGINT)

    def test_sigterm(self):
        self.check(signal.SIGTERM)

    def test_children_survive(self):
        self.inst(sh("echo $$ >> pids; touch began; sleep 0.5; touch done"), "s.json")
        p, out, _ = self.start(self.config({"interval_ms": 10000, "insts": {"s.json": {}}}))
        self.wait_for(lambda: self.exists("began"))
        os.kill(p.pid, signal.SIGTERM)
        self.assertEqual(p.wait(timeout=1), 0)
        self.assertFalse(self.exists("done"))
        self.wait_for(lambda: self.exists("done"), timeout=3)


class Step6Tick(DaemonCase):
    """node 當模組：daemon 不認得 node，只叫 aos-exec 跑一份 argv 是 aos-tick 的 inst。"""

    def setUp(self):
        super().setUp()
        self.node = os.path.join(self.d, "n", "a")
        self.inst({"argv": [TICK], "stderr": INHERIT}, "n/a/inst.json")
        self.write("n/a/.aos/tasks.json", tasks_json({"id": "t", "argv": ["true"]}))

    def seq(self):
        # 第九批拆檔：seq 在 record.json。每格收尾時 tick 把 current 改名成 last、再把新的改名成 current，
        # 中間有一瞬間沒有 current（daemon 一直在跑時讀得到這個空檔），那時就看 last。
        for name in ("current", "last"):
            p = os.path.join(self.node, ".aos", "tick", name, "record.json")
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)["seq"]
            except FileNotFoundError:
                continue
        return 0

    def test_inst_path(self):
        inst = os.path.join(self.node, "inst.json")
        _, out, _ = self.start(self.config({"interval_ms": 100, "insts": {inst: {}}}))
        self.wait_for(lambda: self.seq() >= 3)
        self.wait_for(lambda: len(self.results(out, inst)) >= 3)
        self.assertEqual(set(self.results(out, inst)), {0})

    def test_dir_path(self):
        _, out, _ = self.start(self.config({"interval_ms": 100, "insts": {self.node: {}}}))
        self.wait_for(lambda: len(self.results(out, self.node)) >= 2)
        self.assertEqual(set(self.results(out, self.node)), {0})
        self.assertGreaterEqual(self.seq(), 2)

    def test_blocked(self):
        self.write("n/a/.aos/tick-blocked", "人手暫停")
        _, out, err = self.start(self.config({"interval_ms": 50, "exec_err_path": "/dev/stderr",
                                              "insts": {"n/a": {}}}))
        self.wait_for(lambda: len(self.results(out, "n/a")) >= 3)
        self.assertEqual(set(self.results(out, "n/a")), {0})
        self.assertEqual(self.seq(), 0)
        self.assertFalse(any("blocked" in l for l in list(err)), err)   # 第十六批：擋板檔不印 stderr
        os.remove(os.path.join(self.node, ".aos", "tick-blocked"))
        self.wait_for(lambda: self.seq() >= 2)

    def test_bad_table(self):
        self.write("n/a/.aos/tasks.json", "{")
        _, out, _ = self.start(self.config({"interval_ms": 50, "stop_on_nonzero": True,
                                            "insts": {"n/a": {}}}))
        self.wait_for(lambda: any(l.endswith(" inst=n/a stopped") for l in list(out)))
        self.assertEqual(self.results(out, "n/a"), [1])

    def test_two_daemons(self):
        # 兩份設定檔（同一份會被鎖檔擋下、回 1，第十九批）
        cfg = self.config({"interval_ms": 10, "insts": {"n/a": {}}})
        cfg2 = self.config({"interval_ms": 10, "insts": {"n/a": {}}}, "config2.json")
        _, out1, _ = self.start(cfg)
        _, out2, _ = self.start(cfg2)
        self.wait_for(lambda: len(self.results(out1, "n/a")) >= 5 and len(self.results(out2, "n/a")) >= 5)
        self.assertEqual(set(self.results(out1, "n/a") + self.results(out2, "n/a")), {0})
        self.assertGreaterEqual(self.seq(), 1)


if __name__ == "__main__":
    unittest.main()
