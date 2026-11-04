"""〔llmcall〕單次傳輸、八個崩潰點 ×3、軟 token 帳與遲到人工接回。"""
import errno
import json
import os
import signal
import time
import unittest
from unittest.mock import patch

from llmcallcase import BUDGET, LlmcallCase, R, bg, last_json, read_json, tree, write_json
import aos7_llmcall as lc
from aos7_fs import Unknown


class TestLlmcallLate(LlmcallCase):
    """〔llmcall〕F04／I6：逾時、睡眠中殺整組與人工遲到回覆。"""

    def test_F04_deadline(self):
        req = self.request("late.json", mode="late", delay=3)
        start = time.monotonic()
        p = self.call(req=req, extra=("--deadline", "1"))
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertLess(time.monotonic() - start, 2.5)
        self.assertEqual(self.sends(), 1)
        self.assertEqual(self.audit()["inflight"], R)
        for _ in range(3):
            self.assertEqual(self.call(req=req).returncode, 3)
        self.assertEqual(self.sends(), 1)
        self.assertFalse((self.cd() / "raw.json").exists())

    def test_F04_kill_three_then_adopt(self):
        """三個 C 各在傳輸睡眠中被殺整組；重跑皆 3、不重送、不退款；budget cancel 退 3 不改入口；adopt 後結算。"""
        req = self.request("sleep.json", mode="late", delay=30)
        cs = ("k0", "k1", "k2")
        for c in cs:
            p = self.popen(*self.args(c, req=req))
            self.wait_for(lambda: self.sends(c) == 1)
            os.killpg(p.pid, signal.SIGKILL)
            self.assertEqual(p.wait(12), -9)
            for _ in range(3):
                self.assertEqual(self.call(c, req=req).returncode, 3)
            self.assertEqual(self.sends(c), 1)
            self.assertEqual(self.gw(c)["stage"], "intent")
        self.assertEqual(self.audit()["inflight"], 3 * R)
        before, ledger = self.gwpath("k0").read_bytes(), self.audit()
        p = self.cli("cancel", "budget/llm", "--holder", "author", "--request", "k0", binary=BUDGET)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertEqual(self.gwpath("k0").read_bytes(), before)
        self.assertEqual(self.audit()["log"], ledger["log"])
        for c in cs:
            self.assertEqual(self.adopt(c).returncode, 0)
            self.assertEqual(self.gw(c)["stage"], "intent")
            raw = read_json(str(self.cd(c) / "raw.json"))
            self.assertEqual(raw["source"], "adopted")
            obj = self.assert_receipt(self.call(c, req=req))
            self.assertEqual((obj["text"], obj["raw_sha"]), ("遲到原文", bg.sha(raw)))
            self.assertEqual(self.sends(c), 1)
        L = self.audit()
        self.assertEqual((L["inflight"], L["used"], [e["op"] for e in L["log"]].count("settle")), (0, 3 * R, 3))

    def test_F04_cancel_intent_guard(self):
        self.intent(point="after-send")
        before = self.gwpath().read_bytes()
        ledger = self.audit()
        p = self.cli("cancel", "budget/llm", "--holder", "author", "--request", "c",
                     binary=BUDGET)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertEqual(self.gwpath().read_bytes(), before)
        after = self.audit()
        for k in ("available", "inflight", "used", "ops", "seq", "log"):
            self.assertEqual(after[k], ledger[k])

    def test_I6_wrong_adoption(self):
        self.intent()
        req = read_json(str(self.cd() / "request.json"))
        good = {"call_id": "c", "req_sha": req["req_sha"], "reply": {"status": "ok"}}
        for changes in ({"call_id": "other"}, {"req_sha": "wrong"}, {"reply": []}):
            before = tree(self.node / "llmcall"), tree(self.node / "budget")
            p = self.adopt(obj=dict(good, **changes))
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
            self.assertFalse((self.cd() / "raw.json").exists())
            self.assertEqual((tree(self.node / "llmcall"), tree(self.node / "budget")), before)
        self.assertEqual(self.adopt().returncode, 0)
        before = tree(self.node / "llmcall"), tree(self.node / "budget")
        self.assertEqual(self.adopt().returncode, 1)
        self.assertEqual((tree(self.node / "llmcall"), tree(self.node / "budget")), before)
        self.assert_receipt(self.call())
        self.assertEqual(self.adopt().returncode, 1)
        self.audit()


if __name__ == "__main__":
    unittest.main()
