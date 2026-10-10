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


class TestLlmcallCrash(LlmcallCase):
    """〔llmcall〕F01／F02：同 C 三次 arm，再恢復、獨立核帳與回條重印。"""

    def crash_case(self, point, expected=0, sends=1):
        """三個獨立 C 各在 point 真 SIGKILL 一次（首跑必須 -9），之後同 C 恢復；再跑無崩潰基準比對。"""
        baseline = self.assert_receipt(self.call("baseline"))
        cs = ["%s-%d" % (point, i) for i in range(3)]
        for c in cs:
            self.arm(point)
            p = self.call(c)
            self.assertEqual(p.returncode, -9, p.stdout + p.stderr)
            self.assertFalse((self.node / "llmcall" / ".crash").exists())
            self.assertLessEqual(self.sends(c), 1)
            raw_path = self.cd(c) / "raw.json"
            raw_before = raw_path.read_bytes() if raw_path.exists() else None
            gw_before = self.gwpath(c).read_bytes() if self.gwpath(c).exists() else None
            ledger = self.audit()
            p = self.call(c)
            self.assertEqual(p.returncode, expected, p.stdout + p.stderr)
            self.assertEqual(self.sends(c), sends)
            ledger = self.audit()
            ops = [e["op"] for e in ledger["log"] if e["kid"] == self.kid(c)]
            self.assertEqual(ops, ["reserve", "settle"] if expected == 0 else ["reserve"])
            if raw_before is not None:
                self.assertEqual(raw_path.read_bytes(), raw_before)       # raw 一經存下不再改
            if expected == 3:
                self.assertEqual(ledger["ops"][self.kid(c)]["stage"], "reserved")
                self.assertEqual(self.gw(c)["stage"], "intent")
                self.assertEqual(self.gwpath(c).read_bytes(), gw_before)
                self.assertFalse(raw_path.exists())
                for _ in range(2):
                    self.assertEqual(self.call(c).returncode, 3)
                self.assertEqual(self.sends(c), sends)
                continue
            obj = self.assert_receipt(p)
            raw = read_json(str(raw_path))
            done = self.gw(c)
            self.assertEqual((obj["raw_sha"], done["raw_sha"]), (bg.sha(raw), bg.sha(raw)))
            self.assertEqual(done["at"], raw["at"])                          # 確定性：done.at 取 raw.at
            if gw_before is not None and json.loads(gw_before).get("stage") == "done":
                self.assertEqual(self.gwpath(c).read_bytes(), gw_before)   # 已有 done 不重寫
            for k in ("outcome", "used", "usage", "overrun", "billing"):
                self.assertEqual(obj[k], baseline[k], k)
            self.assertEqual(obj["settle"]["used"], baseline["settle"]["used"])
            frozen, gw_bytes = tree(self.cd(c)), self.gwpath(c).read_bytes()
            replay = self.call(c)
            self.assertEqual((replay.returncode, replay.stdout), (0, p.stdout))
            self.assertEqual((tree(self.cd(c)), self.gwpath(c).read_bytes()), (frozen, gw_bytes))
        ledger = self.audit()
        self.assertEqual(set(ledger["ops"]), {self.kid(c) for c in cs + ["baseline"]})     # 沒有另造 K
        n_ok = 4 if expected == 0 else 1
        self.assertEqual(ledger["inflight"], (4 - n_ok) * R)
        self.assertEqual(ledger["available"], ledger["initial"] - 4 * R)    # U=R：結算或在途都是 R，未知不退款

    def test_F01_after_request(self):
        self.crash_case("after-request")

    def test_F01_after_reserve(self):
        self.crash_case("after-reserve")

    def test_F01_after_intent(self):
        self.crash_case("after-intent", 3, 0)

    def test_F01_after_send(self):
        self.crash_case("after-send", 3, 1)

    def test_F02_after_raw(self):
        self.crash_case("after-raw")

    def test_F02_after_done(self):
        self.crash_case("after-done")

    def test_F02_after_settle(self):
        self.crash_case("after-settle")

    def test_F02_after_receipt(self):
        self.crash_case("after-receipt")


if __name__ == "__main__":
    unittest.main()
