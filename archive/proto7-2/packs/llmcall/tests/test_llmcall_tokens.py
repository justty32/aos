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


class TestLlmcallTokens(LlmcallCase):
    """〔llmcall〕F03：計量、缺 usage、拒絕與最後額度競爭。"""

    def test_F03_partial(self):
        bd = self.up("partial", amount=1000)
        req = self.request("partial.json", usage=120)
        obj = self.assert_receipt(self.call(req=req, budget="partial"))
        self.assertEqual((obj["used"], obj["usage"]["total_tokens"], obj["settle"]["used"]), (120, 120, 120))
        ledger = self.audit(bd)
        self.assertEqual((ledger["available"], ledger["inflight"], ledger["used"]), (880, 0, 120))

    def test_F03_equal(self):
        obj = self.assert_receipt(self.call())
        self.assertEqual((obj["used"], obj["overrun"], obj["billing"], obj["settle"]["used"]), (R, 0, "final", R))
        self.assertEqual(obj["text"], '{"v":1,"mode":"keep"}')
        self.assertEqual(self.audit()["used"], R)

    def test_F03_no_usage(self):
        req = self.request("pending.json", mode="no_usage", text="候選仍交付")
        obj = self.assert_receipt(self.call(req=req), 4)
        self.assertEqual((obj["billing"], obj["used"], obj["settle"], obj["text"]), ("pending", None, None, "候選仍交付"))
        self.assertNotIn("used", self.gw())
        self.assertFalse((self.cd() / "receipt.json").exists())
        self.assertEqual(self.audit()["inflight"], R)
        before = self.gwpath().read_bytes()
        replay = self.call(req=req)
        self.assertEqual((replay.returncode, replay.stdout), (4, json.dumps(obj, ensure_ascii=False) + "\n"))
        self.assertEqual(self.sends(), 1)
        self.assertEqual(self.gwpath().read_bytes(), before)
        self.assertEqual([e["op"] for e in self.audit()["log"]], ["reserve"])

    def test_F03_overrun(self):
        req = self.request("over.json", mode="over", usage=R + 50)
        for c in ("over1", "over2"):
            obj = self.assert_receipt(self.call(c, req=req), 4)
            self.assertEqual((obj["used"], obj["overrun"], obj["billing"]), (R, 50, "overrun"))
            self.assertEqual((obj["settle"]["used"], obj["settle"]["overrun"]), (R, 50))
            self.assertEqual(self.call(c, req=req).stdout, json.dumps(obj, ensure_ascii=False) + "\n")
        self.assertEqual(self.audit()["overrun"], 100)

    def test_F03_race_last_amount(self):
        bd = self.up("race", amount=R)
        ps = [self.popen(*self.args(c, budget="race")) for c in ("one", "two")]
        results = []
        for p in ps:
            out, err = p.communicate(timeout=12)
            results.append((p.returncode, json.loads(out.strip().splitlines()[-1])))
            if p.returncode == 0:
                self.assertEqual(err, "")
            else:
                self.assertEqual(len(err.splitlines()), 1)
                self.assertTrue(err.startswith("aos7-llmcall: "))
        self.assertEqual(sorted(rc for rc, _ in results), [0, 1])
        denied = next(obj for rc, obj in results if rc == 1)
        self.assertEqual((denied["outcome"], denied["stage"]), ("denied", "reserve"))
        answered = next(obj for rc, obj in results if rc == 0)
        self.assertEqual(answered["bound"], "soft")
        ledger = self.audit(bd)
        self.assertEqual((ledger["available"], ledger["inflight"], ledger["used"], len(ledger["ops"])), (0, 0, R, 1))
        self.assertEqual(sum(self.sends(c) for c in ("one", "two")), 1)

    def test_reject_and_fail(self):
        req = self.request("reject.json", mode="reject")
        obj = self.assert_receipt(self.call("reject", req=req), 1)
        self.assertEqual((obj["outcome"], obj["used"], obj["billing"], obj["settle"]["used"]), ("rejected", 0, "final", 0))
        self.assertEqual(self.audit()["available"], 10000)
        req = self.request("fail.json", mode="fail")
        obj = self.assert_receipt(self.call("fail", req=req), 1)
        self.assertEqual((obj["outcome"], obj["used"]), ("failed", R))
        self.assertEqual(self.audit()["used"], R)


if __name__ == "__main__":
    unittest.main()
