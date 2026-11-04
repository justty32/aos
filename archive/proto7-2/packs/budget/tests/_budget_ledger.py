"""〔budget〕grant／帳／入口：正常與競爭、崩潰（真 SIGKILL）、時間與失敗、獨立核帳（packs/budget/spec.md）。

這裡不起 daemon：帳任務是 `aos7-budget ledger` 子程序（同 keep 任務的本體），時鐘直接寫 round.json。
SIGKILL 點用包自己的鉤子（預算資料夾的 `.crash`），不碰核心的 AOS7_TEST_*。接 step 與真 daemon 的在 test_budget_step.py。
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import unittest

from budgetcase import BudgetCase, grant, last_json, set_clock
import aos7_budget as bg
from aos7_fs import read_json, write_json

KILLED = -signal.SIGKILL


class LedgerCase(BudgetCase):
    def setUp(self):
        super().setUp()
        self.node = os.path.join(self.root, "a")

    def up(self, g=None, clock=5):
        self.bd = self.setup_budget(self.node, g, clock=clock)
        self.lp = self.start_ledger(self.node)
        return self.bd

    def restart_ledger(self, check=None):
        self.assertEqual(self.lp.wait(10), KILLED, "帳任務沒在鉤子點被殺")
        if check is not None:
            check()
        self.lp = self.start_ledger(self.node)

    def kid(self, req, holder="api"):
        return bg.kid_of(bg.make_key("demo", holder, req))

    def assert_cancelled(self, bd, request, gateway="fakeapi", digest=None):
        key = bg.make_key("demo", "api", request)
        kid = bg.kid_of(key)
        rec = self.gw(bd, kid)
        self.assertEqual(rec, {"stage": "done", "kid": kid, "key": key, "digest": digest,
                               "gateway": gateway, "call_id": request, "outcome": "cancelled", "used": 0,
                               "usage": None, "overrun": 0, "billing": "final", "raw_sha": None, "at": rec["at"]})
        self.assertIsInstance(rec["at"], str)


