"""kernel 骨架（spec.md）：設定、state、快照、執行順序、送出與核對。驗收條號見 kernel-pack §9。"""
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from functools import partial
from unittest.mock import patch

from kernelcase import BRAIN, FAKE, KERNEL, PACK, PY, RUN, CoreCase, KernelMixin, read_json, write_json
from base import DaemonCase
from aos7_kernel_state import load_state, sha_of, snapshot


class KernelUnderDaemon(KernelMixin, DaemonCase):
    ctl = DaemonCase.ctl     # KernelMixin.ctl（讀目標 ctl.json）同名；這裡要 daemon 的那個

    def setUp(self):
        super().setUp()
        self.setup_kernel(start_brain=False)

    def test_kernel_as_keep_task(self):
        """K01 整合：kernel 當普通 keep 任務由真 daemon 起、收真 tock；第 3 個 tock 的決定 kill 掉 brain 當時的 run，keep 重起新 run，kernel 記 done ok、不再追殺新 run。"""
        self.cfg([self.kill_rule(frm=3, until=3)])
        self.set_tasks(self.node, [{"name": "brain", "mode": "keep", "argv": ["sleep", "1000"]},
                                   {"name": "kernel", "mode": "keep", "argv": [PY, "-B", FAKE, "run"]}])
        self.start_daemon(register=("a",))
        kslot = self.slot(self.node, "kernel")
        st = lambda: read_json(os.path.join(kslot, "state.json")) or {}
        done = self.wait_for(lambda: [d for d in st().get("done", []) if d.get("result") == "ok"], 30,
                             "kernel 一直沒記到 kill ok：%s" % st())
        self.assertEqual(len(done), 1)
        killed = done[0]["run"]
        self.wait_for(lambda: (self.brain_run() or 0) > killed, 15, "brain 沒有重起")
        self.assertIsNone(self.exit_of(self.node, "brain"))   # 新 run 活著、沒被追殺
        last = st().get("last_tock", 0)
        self.wait_for(lambda: st().get("last_tock", 0) >= last + 3, 15, "kernel 沒繼續收 tock")
        self.assertEqual([d["run"] for d in st()["done"] if d["op"] == "kill"], [killed])
        self.assertIsNone(read_json(os.path.join(self.brain_slot(), "ctl.json")))


class KernelWithRealRule(KernelMixin, CoreCase):
    def setUp(self):
        super().setUp()
        self.setup_kernel()

    def test_supervise_brain_end_to_end(self):
        """快照接 KR1 的 supervise-brain（正式入口）：task.json 不動、來源鐘前進 → 第 2 回合起算的老化到 2 寄通知（無 mail＝logged），到 4 kill 當時的 run；新 run 在 8 個 tock 內不被追殺。"""
        self.cfg([{"name": "supervise-brain", "no_progress_rounds": 2, "kill_after_rounds": 4, "notify": "you"}],
                 sources=[dict(BRAIN, kind="brain")])
        write_json(os.path.join(self.node, "brain", "task.json"),
                   {"id": "bob-1", "step": 3, "line": "卡住", "stall": 0, "trail": []})
        run, results = self.brain_run(), []
        for n in range(1, 9):
            write_json(os.path.join(self.kslot, "tock.json"), {"run": RUN, "round": n})
            p = self.kernel("run", "--rounds", "1", entry=KERNEL)
            self.assertEqual(p.returncode, 0, self.show(p))
            if self.ctl():
                self.core_round()   # 核心收掉、keep 重起
            self.core_round()       # 來源鐘前進一格
            results = [(d["op"], d["result"]) for d in self.state()["done"]]
        # 新 run 起來 task.json 仍不動＝重建計時，同信不再通知；kill 只有原 run 那一次
        self.assertEqual(results[:2], [("notify", "logged"), ("kill", "ok")], self.state())
        kills = [d for d in self.state()["done"] if d["op"] == "kill"]
        self.assertEqual([k["run"] for k in kills], [run])
        self.assertGreater(self.brain_run(), run)
        self.assertIn("bob-1…", [d for d in self.state()["done"] if d["op"] == "notify"][0]["text"])


if __name__ == "__main__":
    unittest.main()
