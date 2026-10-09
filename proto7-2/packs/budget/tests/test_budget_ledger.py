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


class TestGrant(BudgetCase):
    """〔budget〕grant 判定、時鐘與開帳（不起程序的部分）。"""

    def setUp(self):
        super().setUp()
        self.node = os.path.join(self.root, "a")
        self.bd = self.setup_budget(self.node)
        self.b = bg.Bud(self.bd)

    def judge(self, holder="api", resource="fakeapi.calls", gateway="fakeapi"):
        return bg.judge(self.b, holder, resource, gateway, self.ledger(self.bd))[0]

    def test_ok_and_mismatch(self):
        self.assertEqual(self.judge(), "ok")
        self.assertEqual(self.judge(holder="bob"), "denied")
        self.assertEqual(self.judge(resource="cpu"), "denied")
        self.assertEqual(self.judge(gateway="other"), "denied")

    def test_window_half_open(self):
        """from ≤ c < until：until 那一回合起就到期；from 之前是 not_yet（非終局）。"""
        write_json(os.path.join(self.bd, "grant.json"), grant(**{"from": 3, "until": 7}))
        os.unlink(os.path.join(self.bd, "ledger.json"))
        self.assertTrue(bg.init(self.b)[0])
        for c, want in ((2, "not_yet"), (3, "ok"), (6, "ok"), (7, "denied"), (9, "denied")):
            set_clock(self.node, c)
            self.assertEqual(self.judge(), want, c)
        set_clock(self.node, 7, open_=True)           # 第 8 回合開著＝完成的是 7
        self.assertEqual(bg.completed_tock(self.node), 7)

    def test_clock_unknown_and_backwards(self):
        with open(os.path.join(self.node, ".aos", "round.json"), "w") as f:
            f.write("{bad")
        self.assertEqual(self.judge(), "unknown")
        os.unlink(os.path.join(self.node, ".aos", "round.json"))
        self.assertEqual(self.judge(), "unknown")             # 沒有合法值＝未知，不是 0
        L = self.ledger(self.bd)
        L["clock_hw"] = 9
        set_clock(self.node, 8)
        self.assertEqual(bg.judge(self.b, "api", "fakeapi.calls", "fakeapi", L)[0], "unknown")

    def test_grant_changed_or_missing_is_unknown(self):
        write_json(os.path.join(self.bd, "grant.json"), grant(amount=99))
        self.assertEqual(self.judge(), "unknown")             # 開帳後改 grant＝未知，不是新額度
        os.unlink(os.path.join(self.bd, "grant.json"))
        self.assertEqual(self.judge(), "unknown")             # 讀不到不當沒有限制

    def test_child_grant_refused(self):
        """子 grant（parent 或 delegate 不是 false）：開帳拒絕、判定 denied。"""
        for bad in (grant(parent="g0"), grant(delegate=True), {k: v for k, v in grant().items() if k != "delegate"}):
            with self.subTest(bad=bad):
                os.unlink(os.path.join(self.bd, "ledger.json"))
                write_json(os.path.join(self.bd, "grant.json"), bad)
                r = self.cli(self.node, "init", "budget/demo")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertFalse(os.path.exists(os.path.join(self.bd, "ledger.json")))
                self.assertTrue(bg.is_child(bad))
                write_json(os.path.join(self.bd, "grant.json"), grant())
                self.assertTrue(bg.init(self.b)[0])

    def test_init_refuses_existing(self):
        r = self.cli(self.node, "init", "budget/demo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("已存在", r.stdout)


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


class TestNormal(LedgerCase):
    """〔budget〕正常與競爭：消耗 1、搶最後 1、同鍵並行、異內容、不符、拒絕計 0、失敗計 1。"""

    def test_consume_one(self):
        bd = self.up()
        rc, out = self.call(self.node, "r1", payload=self.payload(self.node, "p.json", echo="hi"))
        self.assertEqual(rc, 0, out)
        self.assertEqual((out["outcome"], out["used"], out["response"]["echo"]), ("accepted", 1, "hi"))
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], L["inflight"], L["used"]), (2, 0, 1))
        self.assertEqual(self.backend(bd)["accepted"], 1)
        self.assertEqual((os.listdir(os.path.join(bd, "inbox")), os.listdir(os.path.join(bd, "receipts"))), ([], []))
        st = json.loads(self.cli(self.node, "status", "budget/demo", "--holder", "api", "--request", "r1").stdout)
        self.assertEqual((st["stage"], st["gateway"]["outcome"]), ("settled", "accepted"))

    def test_race_last_unit(self):
        """額度 1，六個不同 K 同時搶：恰一個成功，其餘 denied（不入帳）。"""
        bd = self.up(grant(amount=1))
        ps = [self.popen(self.node, *self.call_args("r%d" % i)) for i in range(6)]
        rcs = sorted(p.wait(30) for p in ps)
        self.assertEqual(rcs, [0, 1, 1, 1, 1, 1])
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], L["used"], len(L["ops"])), (0, 1, 1))

    def test_same_key_concurrent(self):
        """同 K 同內容六個並行：全部回同一個成功結果，後端只受理一次、只扣一次。"""
        bd = self.up()
        ps = [self.popen(self.node, *self.call_args("same")) for _ in range(6)]
        outs = [(p.wait(30), last_json(p.stdout.read())) for p in ps]
        self.assertEqual({rc for rc, _ in outs}, {0}, outs)
        self.assertEqual({o["settle"]["seq"] for _, o in outs}, {2})
        L = self.audit(bd, final=True)
        self.assertEqual((L["used"], len(L["log"]), self.backend(bd)["accepted"]), (1, 2, 1))

    def test_same_key_other_content_conflict(self):
        bd = self.up()
        self.assertEqual(self.call(self.node, "k")[0], 0)
        rc, out = self.call(self.node, "k", payload=self.payload(self.node, "p.json", echo="other"))
        self.assertEqual((rc, out["outcome"]), (1, "conflict"), out)
        rc, out = self.call(self.node, "k", extra=("--amount", "2"))
        self.assertEqual((rc, out["outcome"]), (1, "conflict"), out)
        self.assertEqual(self.audit(bd, final=True)["used"], 1)

    def test_mismatch_denied(self):
        """持有人、資源、入口不符：reserve 被拒、不入帳。"""
        bd = self.up()
        for kw in ({"holder": "bob"}, {"extra": ("--resource", "cpu.ms")}):
            rc, out = self.call(self.node, "x", **kw)
            self.assertEqual((rc, out["outcome"], out["stage"]), (1, "denied", "reserve"), out)
        shutil.rmtree(os.path.join(self.node, "budget"))
        self.lp.kill()
        bd = self.up(grant(gateway="other"))
        rc, out = self.call(self.node, "x")
        self.assertEqual((rc, out["outcome"]), (1, "denied"), out)
        self.assertEqual(self.audit(bd)["seq"], 0)

    def test_reject_zero_fail_one(self):
        """後端明確拒絕計 0、退回預留；已受理後處理失敗仍計 1。"""
        bd = self.up()
        rc, out = self.call(self.node, "rej", payload=self.payload(self.node, "r.json", mode="reject"))
        self.assertEqual((rc, out["outcome"], out["used"]), (1, "rejected", 0), out)
        rc, out = self.call(self.node, "fail", payload=self.payload(self.node, "f.json", mode="fail"))
        self.assertEqual((rc, out["outcome"], out["used"]), (1, "failed", 1), out)
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], L["used"], self.backend(bd)["accepted"]), (2, 1, 1))


class TestCrash(LedgerCase):
    """〔budget〕崩潰：帳與包裝程式在各持久提交前後被 SIGKILL，重開／重跑同 K 只把沒做完的做完。"""

    def test_ledger_points(self):
        for point in ("reserve-before-commit", "reserve-after-commit", "settle-before-commit", "settle-after-commit"):
            with self.subTest(point=point):
                bd = self.up()
                self.crash_at(bd, point)
                p = self.popen(self.node, *self.call_args("r1"))
                def check():
                    L = self.audit(bd)                           # 重起前核崩潰快照
                    kid = self.kid("r1")
                    seq, balances, stage = {
                        "reserve-before-commit": (0, (3, 0, 0), None),
                        "reserve-after-commit": (1, (2, 1, 0), "reserved"),
                        "settle-before-commit": (1, (2, 1, 0), "reserved"),
                        "settle-after-commit": (2, (2, 0, 1), "settled"),
                    }[point]
                    self.assertEqual(L["seq"], seq)
                    self.assertEqual((L["available"], L["inflight"], L["used"]), balances)
                    if stage is None:
                        self.assertNotIn(kid, L["ops"])
                    else:
                        self.assertEqual(L["ops"][kid]["stage"], stage)
                    if point == "settle-before-commit":
                        self.assertEqual(self.gw(bd, kid)["stage"], "done")
                self.restart_ledger(check)
                self.assertEqual(p.wait(30), 0, p.stderr.read())
                L = self.audit(bd, final=True)
                self.assertEqual((L["used"], len(L["log"]), self.backend(bd)["accepted"]), (1, 2, 1))
                self.assertFalse(os.path.exists(os.path.join(bd, ".crash")))
                self.lp.kill()
                self.lp.wait()
                shutil.rmtree(os.path.join(self.node, "budget"))

    def test_wrapper_points(self):
        """包裝程式在 reserve 後、准入意圖後、後端效果後（回條未寫）、入口回條後、結算後被殺：重跑同 K 不重扣、不重做。"""
        for point in ("call-after-reserve", "gateway-after-intent", "backend-after-effect", "gateway-after-receipt",
                      "call-after-settle"):
            with self.subTest(point=point):
                bd = self.up()
                self.crash_at(bd, point)
                rc, out = self.call(self.node, "r1")
                self.assertEqual(rc, KILLED, out)
                self.audit(bd)
                rc, out = self.call(self.node, "r1")
                self.assertEqual((rc, out["outcome"]), (0, "accepted"), out)
                self.assertEqual(self.call(self.node, "r1")[0], 0)        # 再重播一次
                L = self.audit(bd, final=True)
                self.assertEqual((L["used"], len(L["log"]), self.backend(bd)["accepted"]), (1, 2, 1))
                self.lp.kill()
                self.lp.wait()
                shutil.rmtree(os.path.join(self.node, "budget"))

    def test_unknown_then_evidence(self):
        """准入意圖寫了就被殺：settle 回 unknown、預留留著（不退）；補上證據（重跑同 K）才結算。"""
        bd = self.up()
        self.crash_at(bd, "gateway-after-intent")
        self.assertEqual(self.call(self.node, "u")[0], KILLED)
        self.assertEqual(self.gw(bd, self.kid("u"))["stage"], "intent")
        r = self.cli(self.node, "settle", "budget/demo", "--holder", "api", "--request", "u")
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertEqual(last_json(r.stdout)["result"], "unknown")
        L = self.audit(bd)
        self.assertEqual((L["available"], L["inflight"]), (2, 1))
        self.assertEqual(self.call(self.node, "u")[0], 0)
        self.assertEqual(self.audit(bd, final=True)["used"], 1)

    def test_cancel_then_late_run(self):
        """預留後取消：終局 cancelled，晚到的 run(K) 不執行、結算 0、額度退回。"""
        bd = self.up()
        self.crash_at(bd, "call-after-reserve")
        self.assertEqual(self.call(self.node, "c")[0], KILLED)
        r = self.cli(self.node, "cancel", "budget/demo", "--holder", "api", "--request", "c")
        self.assertEqual((r.returncode, last_json(r.stdout)["outcome"]), (0, "cancelled"), r.stdout)
        rc, out = self.call(self.node, "c")
        self.assertEqual((rc, out["outcome"], out["used"]), (1, "cancelled", 0), out)
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], L["used"], self.backend(bd)["effects"]), (3, 0, {}))

    def test_cancel_after_effect_refused(self):
        """後端已受理（入口回條未寫）時取消：查回效果、寫成 accepted，取消不成；結算 1。"""
        bd = self.up()
        self.crash_at(bd, "backend-after-effect")
        self.assertEqual(self.call(self.node, "e")[0], KILLED)
        r = self.cli(self.node, "cancel", "budget/demo", "--holder", "api", "--request", "e")
        self.assertEqual((r.returncode, last_json(r.stdout)["outcome"]), (1, "accepted"), r.stdout)
        self.assertEqual(self.call(self.node, "e")[0], 0)
        self.assertEqual(self.audit(bd, final=True)["used"], 1)

    def test_cancel_run_race(self):
        """十個 K 各自同時跑 call 與 cancel：每個 K 恰為「後端受理」或「已取消」之一，不雙花；途中每份帳快照都守恆。"""
        bd = self.up(grant(amount=10))
        snaps, stop = [], threading.Event()

        def sampler():
            while not stop.is_set():
                L = read_json(os.path.join(bd, "ledger.json"))
                if isinstance(L, dict):
                    snaps.append(L)
                time.sleep(0.005)
        t = threading.Thread(target=sampler)
        t.start()
        try:
            ps = []
            for i in range(10):
                ps.append(self.popen(self.node, *self.call_args("q%d" % i)))
                ps.append(self.popen(self.node, "cancel", "budget/demo", "--holder", "api", "--request", "q%d" % i))
            for p in ps:
                p.wait(30)
            for i in range(10):                        # 取消贏了的，call 可能停在 settle 前：重跑同 K 收尾
                self.assertIn(self.call(self.node, "q%d" % i)[0], (0, 1))
        finally:
            stop.set()
            t.join()
        L = self.audit(bd, final=True)
        b = self.backend(bd)
        for i in range(10):
            k = self.kid("q%d" % i)
            g = self.gw(bd, k)
            self.assertIn(g["outcome"], ("accepted", "cancelled"))
            self.assertEqual(g["outcome"] == "accepted", k in b["effects"], k)
        self.assertEqual(L["used"], b["accepted"])
        final_log = L["log"]
        for s in snaps:
            self.assertEqual(s["available"] + s["inflight"] + s["used"], s["initial"])
            self.assertTrue(min(s["available"], s["inflight"], s["used"]) >= 0)
            self.assertEqual(s["log"], final_log[:len(s["log"])], "帳快照不是最後 log 的前綴")


class TestTime(LedgerCase):
    """〔budget〕時間與失敗：到期、未生效、壞鐘、時鐘倒退、壞帳、帳不見不自動開。"""

    def test_reserved_then_expired_first_run_denied(self):
        """到期前 reserve、到期後首次准入被擋：入口終局 denied、結算 0、額度退回。"""
        bd = self.up(grant(until=10), clock=9)
        self.crash_at(bd, "call-after-reserve")
        self.assertEqual(self.call(self.node, "t")[0], KILLED)
        set_clock(self.node, 10)
        rc, out = self.call(self.node, "t")
        self.assertEqual((rc, out["outcome"], out["used"]), (1, "denied", 0), out)
        L = self.audit(bd, final=True)
        self.assertEqual((L["available"], self.backend(bd)["effects"]), (3, {}))

    def test_reserve_after_expiry_denied(self):
        bd = self.up(grant(until=10), clock=10)
        rc, out = self.call(self.node, "t")
        self.assertEqual((rc, out["outcome"], out["stage"]), (1, "denied", "reserve"), out)
        self.assertEqual(self.audit(bd)["seq"], 0)

    def test_admitted_then_expired_still_settles(self):
        """已准入（意圖寫了）後到期：恢復不再查效期，照常受理並結算 1。"""
        bd = self.up(grant(until=10), clock=9)
        self.crash_at(bd, "gateway-after-intent")
        self.assertEqual(self.call(self.node, "t")[0], KILLED)
        set_clock(self.node, 15)
        rc, out = self.call(self.node, "t")
        self.assertEqual((rc, out["outcome"]), (0, "accepted"), out)
        self.assertEqual(self.audit(bd, final=True)["used"], 1)

    def test_not_yet_is_not_terminal(self):
        bd = self.up(grant(**{"from": 5}), clock=3)
        rc, out = self.call(self.node, "n")
        self.assertEqual((rc, out["outcome"]), (3, "unknown"), out)
        self.assertEqual(self.audit(bd)["seq"], 0)
        set_clock(self.node, 5)
        self.assertEqual(self.call(self.node, "n")[0], 0)

    def test_bad_clock(self):
        """壞鐘：新 reserve 未知（不入帳）；已有入口證據的結算照做（不看時鐘）；時鐘倒退＝未知。"""
        bd = self.up(clock=9)
        self.crash_at(bd, "gateway-after-receipt")
        self.assertEqual(self.call(self.node, "s")[0], KILLED)
        rnd = os.path.join(self.node, ".aos", "round.json")
        with open(rnd, "w") as f:
            f.write("{bad")
        rc, out = self.call(self.node, "new")
        self.assertEqual((rc, out["outcome"], out["stage"]), (3, "unknown", "reserve"), out)
        rc, out = self.call(self.node, "s")
        self.assertEqual((rc, out["outcome"]), (0, "accepted"), out)
        set_clock(self.node, 4)                            # 帳看過 9
        rc, out = self.call(self.node, "back")
        self.assertEqual((rc, out["outcome"]), (3, "unknown"), out)
        L = self.audit(bd, final=True)
        self.assertEqual((len(L["ops"]), L["used"]), (1, 1))

    def test_bad_ledger_refuses(self):
        """壞帳：帳任務不受理（記 error.json、請求留著），包裝程式等滿耐性回 3；修好後同一請求照常處理、只扣一次。"""
        bd = self.up(clock=5)
        lpath = os.path.join(bd, "ledger.json")
        with open(lpath) as f:
            good = f.read()
        with open(lpath, "w") as f:
            f.write("{bad")
        p = self.popen(self.node, *self.call_args("b", extra=("--patience", "1")))
        self.wait_for(lambda: (read_json(os.path.join(bd, "error.json")) or {}).get("kind") == "ledger", 10,
                      "帳沒記錯")
        self.assertEqual(len(os.listdir(os.path.join(bd, "inbox"))), 1)
        self.assertIsNone(p.poll())
        set_clock(self.node, 6)
        self.assertEqual(p.wait(10), 3)
        with open(lpath) as f:
            self.assertEqual(f.read(), "{bad")              # 不當空帳覆寫
        with open(lpath, "w") as f:
            f.write(good)
        self.wait_for(lambda: not os.listdir(os.path.join(bd, "inbox")), 10, "修好後沒處理留著的請求")
        self.assertEqual(self.call(self.node, "b")[0], 0)
        L = self.audit(bd, final=True)
        self.assertEqual((L["used"], len(L["log"])), (1, 2))

    def test_missing_ledger_not_reopened(self):
        bd = self.up()
        os.unlink(os.path.join(bd, "ledger.json"))
        rc, out = self.call(self.node, "m", extra=("--patience", "0"))
        self.assertEqual(rc, 3, out)
        self.wait_for(lambda: (read_json(os.path.join(bd, "error.json")) or {}).get("kind") == "ledger", 10)
        self.assertFalse(os.path.exists(os.path.join(bd, "ledger.json")))


class TestBounds(LedgerCase):
    """〔budget〕loop6：後端讀寫故障回 3（A6-02）、時鐘水位推高、孤兒回條、退役拒收。"""

    def fault_call(self, req, env, cmd="call", **kw):
        """在故障下跑 call／cancel／settle：回 (退出碼, 最後一行 JSON)，並確認 stdout 恰一行 JSON、stderr 沒有 traceback。"""
        args = self.call_args(req, **kw) if cmd == "call" else (cmd, "budget/demo", "--holder", "api", "--request", req)
        r = self.cli(self.node, *args, env=env)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1, r.stdout)
        return r.returncode, last_json(r.stdout)

    def test_payload_eio_and_bad_input(self):
        bd = self.up()
        payload = self.payload(self.node, "payload.json", echo="hi")
        hits = os.path.join(self.root, "hits.txt")
        env = {"AOS7_TEST_FAULT": "open:*/payload.json:EIO", "AOS7_TEST_FAULT_HITS": hits}
        rc, out = self.fault_call("p", env, payload=payload)
        self.assertEqual((rc, out["outcome"], out["stage"]), (3, "unknown", "payload"))
        with open(hits) as f:
            self.assertIn("payload.json", f.read(), "EIO 沒打中")
        os.unlink(payload)
        for bad in (None, "{bad"):
            if bad is not None:
                with open(payload, "w") as f:
                    f.write(bad)
            r = self.cli(self.node, *self.call_args("p", payload=payload))
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1)
            self.assertEqual(r.stdout, "")
        self.assertEqual(self.audit(bd)["seq"], 0)
        self.assertEqual(os.listdir(os.path.join(bd, "inbox")), [])

    def test_replay_eio_preserves_out(self):
        bd = self.up()
        outpath = os.path.join(self.node, "out.json")
        extra = ("--out", outpath)
        self.assertEqual(self.call(self.node, "r", extra=extra)[0], 0)
        with open(outpath, "rb") as f:
            before = f.read()
        hits = os.path.join(self.root, "hits.txt")
        env = {"AOS7_TEST_FAULT": "open:*/gateway/%s.json:EIO" % self.kid("r"),
               "AOS7_TEST_FAULT_HITS": hits}
        rc, out = self.fault_call("r", env, extra=extra)
        self.assertEqual((rc, out["outcome"], out["stage"]), (3, "unknown", "replay"))
        with open(hits) as f:
            self.assertIn(self.kid("r") + ".json", f.read(), "EIO 沒打中")
        with open(outpath, "rb") as f:
            self.assertEqual(f.read(), before)
        rc, out = self.call(self.node, "r", extra=extra)
        self.assertEqual(rc, 0, out)
        self.assertIsNotNone(out["response"])
        self.assertEqual(self.audit(bd, final=True)["used"], 1)

    def test_out_directory_then_replay(self):
        bd = self.up()
        rc, out = self.fault_call("o", None, extra=("--out", self.node))
        self.assertEqual((rc, out["outcome"], out["stage"]), (3, "unknown", "io"))
        L = self.audit(bd, final=True)
        self.assertEqual((L["inflight"], L["used"], self.backend(bd)["accepted"]), (0, 1, 1))
        rc, out = self.call(self.node, "o", extra=("--out", os.path.join(self.node, "out.json")))
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.backend(bd)["accepted"], 1)

    def test_weighted_cost(self):
        bd = self.up()
        self.assertEqual(self.call(self.node, "one")[0], 0)
        self.assertEqual(self.call(self.node, "two", extra=("--amount", "2"))[0], 0)
        L = self.audit(bd, final=True)
        self.assertEqual((L["used"], self.backend(bd)["accepted"], L["available"]), (3, 2, L["initial"] - 3))

    def test_gateway_tmp_sweeps_only_dead_writer(self):
        bd = self.setup_budget(self.node)
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        self.assertEqual(p.wait(10), 0)
        gateway = os.path.join(bd, "gateway")
        os.makedirs(gateway, exist_ok=True)
        dead = os.path.join(gateway, ".x.json.tmp.%d" % p.pid)
        live = os.path.join(gateway, ".y.json.tmp.%d" % os.getpid())
        for path in (dead, live):
            with open(path, "w") as f:
                f.write("{}")
        self.lp = self.start_ledger(self.node)
        self.assertEqual(self.call(self.node, "t")[0], 0)   # 帳處理過請求＝啟動掃描已跑完
        self.assertFalse(os.path.exists(dead), "死亡寫者的暫存檔沒掃")
        self.assertTrue(os.path.exists(live), "活寫者的暫存檔不該掃")

    def test_backend_eio_is_unknown(self):
        """A6-02：已有 intent，後端讀到 EIO：call、cancel 都回 3（非終局），intent 與預留留著；恢復後同 K 只受理一次。"""
        bd = self.up()
        self.crash_at(bd, "gateway-after-intent")
        self.assertEqual(self.call(self.node, "e")[0], KILLED)
        hits = os.path.join(self.root, "hits.txt")
        env = {"AOS7_TEST_FAULT": "open:*/budget/demo/backend.json:EIO", "AOS7_TEST_FAULT_HITS": hits}
        for cmd in ("call", "cancel", "call"):
            rc, out = self.fault_call("e", env, cmd)
            self.assertEqual((rc, out["outcome"]), (3, "unknown"), (cmd, out))
        with open(hits) as f:
            self.assertGreaterEqual(len(f.read().splitlines()), 3, "EIO 沒打中")
        self.assertEqual(self.gw(bd, self.kid("e"))["stage"], "intent")
        L = self.audit(bd)
        self.assertEqual((L["available"], L["inflight"], self.backend(bd)["accepted"]), (2, 1, 0))
        self.assertEqual(self.call(self.node, "e")[0], 0)
        L = self.audit(bd, final=True)
        self.assertEqual((L["used"], self.backend(bd)["accepted"]), (1, 1))

    def test_backend_eacces_is_unknown(self):
        """A6-02：真 EACCES（backend.json 權限 000）：rc 3、內容不變；恢復權限後同 K 只受理一次。"""
        if os.geteuid() == 0:
            self.skipTest("root 讀得到 000 的檔，造不出 EACCES")
        bd = self.up()
        self.assertEqual(self.call(self.node, "seed")[0], 0)
        self.crash_at(bd, "gateway-after-intent")
        self.assertEqual(self.call(self.node, "r")[0], KILLED)
        bp = os.path.join(bd, "backend.json")
        with open(bp, "rb") as f:
            before = f.read()
        os.chmod(bp, 0)
        try:
            rc, out = self.fault_call("r", None)
        finally:
            os.chmod(bp, 0o644)
        self.assertEqual((rc, out["outcome"]), (3, "unknown"), out)
        with open(bp, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(self.audit(bd)["inflight"], 1)
        self.assertEqual(self.call(self.node, "r")[0], 0)
        L = self.audit(bd, final=True)
        self.assertEqual((L["used"], self.backend(bd)["accepted"]), (2, 2))

    def test_clock_hw_rises_on_denied_and_replay(self):
        """clock_hw 每次帳讀到合法 c 就推高：到期被拒、重播也算；之後退鐘到這之下＝未知，不放行。"""
        bd = self.up(grant(until=10), clock=5)
        self.assertEqual(self.call(self.node, "a")[0], 0)
        set_clock(self.node, 10)
        self.assertEqual(self.call(self.node, "late")[0], 1)               # 到期拒絕，不入帳
        self.assertEqual(self.ledger(bd)["clock_hw"], 10)
        set_clock(self.node, 12)
        self.assertEqual(self.call(self.node, "a")[0], 0)                  # 重播
        self.assertEqual(self.ledger(bd)["clock_hw"], 12)
        set_clock(self.node, 6)
        rc, out = self.call(self.node, "back")
        self.assertEqual((rc, out["outcome"]), (3, "unknown"), out)
        self.assertEqual(self.ledger(bd)["clock_hw"], 12)                  # 退鐘不拉低
        self.assertEqual(self.audit(bd, final=True)["seq"], 2)

    def test_orphan_receipts_swept_and_replay_same(self):
        """孤兒回條：K 已結算、沒人讀的回條，滿 ORPHAN_ROUNDS 個本 node 回合才刪；重播回條跟刪掉的一樣；在途 K 的不刪。"""
        bd = self.up(clock=5)
        self.assertEqual(self.call(self.node, "s")[0], 0)
        b = bg.Bud(bd)
        key = bg.make_key("demo", "api", "s")
        content = self.ledger(bd)["ops"][self.kid("s")]["content"]
        paths = [bg.submit(b, "reserve", key, content), bg.submit(b, "settle", key)]    # 送了不讀＝呼叫端死了
        self.crash_at(bd, "call-after-reserve")
        self.assertEqual(self.call(self.node, "p")[0], KILLED)                           # p 只預留（在途）
        paths.append(bg.submit(b, "reserve", bg.make_key("demo", "api", "p"),
                               self.ledger(bd)["ops"][self.kid("p")]["content"]))
        self.wait_for(lambda: all(os.path.exists(p) for p in paths), 10, "帳沒發回條")
        orphans = [read_json(p) for p in paths[:2]]
        for c in (6, 7, 8):                       # 帳在 c=6 那輪第一次掃到它們，滿 3 回合是 c=9
            set_clock(self.node, c)
            time.sleep(0.3)
            self.assertTrue(all(os.path.exists(p) for p in paths), "還沒滿 %d 回合就刪了" % bg.ORPHAN_ROUNDS)
        set_clock(self.node, 9)
        self.wait_for(lambda: not any(os.path.exists(p) for p in paths[:2]), 10, "孤兒回條沒被掃")
        time.sleep(0.2)
        self.assertTrue(os.path.exists(paths[2]), "在途 K 的回條不該掃")
        again = [bg.ask(b, "reserve", key, content), bg.ask(b, "settle", key)]
        drop = ("at",)
        self.assertEqual([{k: v for k, v in r.items() if k not in drop} for r in again],
                         [{k: v for k, v in r.items() if k not in drop} for r in orphans])
        L = self.audit(bd)
        self.assertEqual((L["used"], L["inflight"], L["seq"]), (1, 1, 3))

    def test_retired_refuses_new(self):
        """退役：retired.json 在＝新 K 拒收（rc 1、不入帳）；已結算的 K 照樣重播；retired.json 讀不到＝未知。"""
        bd = self.up()
        self.assertEqual(self.call(self.node, "old")[0], 0)
        write_json(os.path.join(bd, "retired.json"), {"at": "x", "why": "test"})
        rc, out = self.call(self.node, "new")
        self.assertEqual((rc, out["outcome"]), (1, "denied"), out)
        self.assertIn("退役", out["why"])
        self.assertEqual(self.call(self.node, "old")[0], 0)
        os.unlink(os.path.join(bd, "retired.json"))
        os.mkdir(os.path.join(bd, "retired.json"))                     # 不是一般檔＝讀不到
        rc, out = self.call(self.node, "new", extra=("--patience", "1"))
        self.assertEqual((rc, out["outcome"]), (3, "unknown"), out)
        L = self.audit(bd, final=True)
        self.assertEqual((len(L["ops"]), L["used"]), (1, 1))

if __name__ == "__main__":
    unittest.main()
