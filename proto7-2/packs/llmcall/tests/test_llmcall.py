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


class TestLlmcallIdentity(LlmcallCase):
    """〔llmcall〕I1／I5：固定請求、鎖、兩預算、唯讀 status 與故障邊界。"""

    def test_I1_replay_and_out(self):
        out = str(self.node / "out.json")
        p = self.call(extra=("--logical", "author/work", "--out", out))
        obj = self.assert_receipt(p)
        self.assertEqual(obj["logical"], "author/work")
        before = tree(self.node / "llmcall"), tree(self.node / "budget")
        replay = self.call(extra=("--logical", "different", "--out", out))
        self.assertEqual((replay.returncode, replay.stdout), (0, p.stdout))
        self.assertEqual((tree(self.node / "llmcall"), tree(self.node / "budget")), before)
        self.assertEqual(read_json(out), obj)
        self.assertEqual(self.sends(), 1)
        self.audit()

    def test_I1_conflict_changes_no_files(self):
        # request 比對在 receipt 之前的恢復階段；有 receipt 依凍結流程直接重印。
        self.intent()
        changed = self.request("changed.json", text="另一份請求")
        for kw in ({"req": changed}, {"reserve": R + 1}, {"holder": "other"}):
            before = tree(self.node / "llmcall"), tree(self.node / "budget")
            p = self.call(**kw)
            self.assertEqual((p.returncode, last_json(p)["outcome"]), (1, "conflict"))
            self.assertEqual((tree(self.node / "llmcall"), tree(self.node / "budget")), before)
        self.assertEqual(self.sends(), 0)
        self.assertEqual(self.audit()["seq"], 1)

    def test_I1_conflict_after_receipt(self):
        """已有回條也先比固定請求：異請求／holder／reserve 一律 conflict、不重印舊回條、不寫檔。"""
        self.assert_receipt(self.call())
        changed = self.request("changed.json", text="另一份請求")
        for kw in ({"req": changed}, {"reserve": R + 1}, {"holder": "other"}):
            before = tree(self.node / "llmcall"), tree(self.node / "budget")
            p = self.call(**kw)
            self.assertEqual((p.returncode, last_json(p)["outcome"]), (1, "conflict"), kw)
            self.assertEqual((tree(self.node / "llmcall"), tree(self.node / "budget")), before)

    def test_I3_tampered_done_digest_with_raw(self):
        """有 raw、入口 done 但 digest 被改：conflict，不結算、不重寫入口。"""
        self.arm("after-done")
        self.assertEqual(self.call().returncode, -9)
        rec = self.gw()
        rec["digest"] = "different"
        write_json(str(self.gwpath()), rec)
        before = tree(self.node / "llmcall"), tree(self.node / "budget")
        p = self.call()
        self.assertEqual((p.returncode, last_json(p)["outcome"]), (1, "conflict"))
        self.assertEqual((tree(self.node / "llmcall"), tree(self.node / "budget")), before)
        self.assertEqual(self.sends(), 1)

    def test_bad_deadline_patience(self):
        before = tree(self.node / "budget")
        for extra in (("--deadline", "inf"), ("--deadline", "nan"), ("--deadline", "0"), ("--deadline", "-1"),
                      ("--deadline", "1e9"), ("--patience", "-1")):
            p = self.call(extra=extra)
            self.assertEqual(p.returncode, 2, (extra, p.stdout, p.stderr))
        self.assertFalse((self.node / "llmcall").exists())
        self.assertEqual(tree(self.node / "budget"), before)

    def test_I1_saved_logical_and_intent_digest(self):
        self.arm("after-request")
        self.assertEqual(self.call(extra=("--logical", "original")).returncode, -9)
        obj = self.assert_receipt(self.call(extra=("--logical", "new")))
        self.assertEqual(obj["logical"], "original")
        self.intent("digest")
        path = self.gwpath("digest")
        rec = self.gw("digest")
        rec["digest"] = "different"
        write_json(str(path), rec)
        before = tree(self.node / "llmcall"), tree(self.node / "budget")
        p = self.call("digest")
        self.assertEqual((p.returncode, last_json(p)["outcome"]), (1, "conflict"))
        self.assertEqual((tree(self.node / "llmcall"), tree(self.node / "budget")), before)
        self.assertEqual(self.sends("digest"), 0)
        self.audit()

    def test_I1_bad_input_no_files_or_reserve(self):
        malformed = self.node / "bad.json"
        malformed.write_text("{broken")
        scalar = self.node / "scalar.json"
        write_json(str(scalar), [])
        variants = [{"c": "../escape"}, {"c": ""}, {"c": "a" * 65}, {"c": "中文"},
                    {"holder": ""}, {"reserve": 0}, {"reserve": -1}, {"reserve": "true"},
                    {"req": str(self.node / "absent.json")}, {"req": str(malformed)}, {"req": str(scalar)}]
        before = tree(self.node / "llmcall"), tree(self.node / "budget")
        for kw in variants:
            with self.subTest(kw=kw):
                p = self.call(**kw)
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertEqual((tree(self.node / "llmcall"), tree(self.node / "budget")), before)
        self.assertEqual(self.audit()["seq"], 0)
        self.assertEqual(list((self.bd / "inbox").iterdir()), [])

    def test_I1_two_budgets_same_call(self):
        bd = self.up("other")
        self.assert_receipt(self.call())
        frozen = tree(self.cd())
        obj = self.assert_receipt(self.call(budget="other"))
        self.assertEqual(obj["key"]["budget"], "other")
        self.assertEqual(tree(self.cd()), frozen)
        self.assertNotEqual(self.kid(), self.kid(budget="other"))
        for path in (self.bd, bd):
            self.assertEqual(len(self.audit(path)["ops"]), 1)
        # 假遠端依 call_id 計數，跨預算這裡會記兩次；本地目錄和 K 各自獨立。
        self.assertEqual(self.sends(), 2)

    def test_I1_concurrent_call_busy(self):
        req = self.request("slow.json", mode="late", delay=1)
        p = self.popen(*self.args(req=req))
        self.wait_for(lambda: self.sends() == 1)
        busy = self.call(req=req)
        self.assertEqual((busy.returncode, last_json(busy)["outcome"], last_json(busy)["stage"]),
                         (3, "unknown", "busy"))
        adopted = self.adopt()
        self.assertEqual((adopted.returncode, last_json(adopted)["stage"]), (3, "busy"))
        out, err = p.communicate(timeout=12)
        self.assertEqual(p.returncode, 0, out + err)
        self.assertEqual(self.sends(), 1)
        self.assertEqual(len(self.audit()["ops"]), 1)

    def test_denied_reserve(self):
        bd = self.up("denied", holder="someone")
        p = self.call(budget="denied")
        self.assertEqual((p.returncode, last_json(p)["outcome"], last_json(p)["stage"]), (1, "denied", "reserve"))
        self.assertFalse((self.cd(budget="denied") / "receipt.json").exists())
        self.assertEqual(self.sends(), 0)
        self.assertEqual(self.audit(bd)["seq"], 0)

    def test_denied_after_reserve_and_cancelled(self):
        bd = self.up("expires", until=10)
        self.arm("after-reserve")
        self.assertEqual(self.call(budget="expires").returncode, -9)
        write_json(str(self.node / ".aos" / "round.json"), {"round": 10, "open": False})
        obj = self.assert_receipt(self.call(budget="expires"), 1)
        self.assertEqual((obj["outcome"], obj["used"], obj["text"], obj["raw_sha"]), ("denied", 0, None, None))
        self.assertEqual(self.audit(bd)["inflight"], 0)
        self.arm("after-reserve")
        self.assertEqual(self.call().returncode, -9)
        p = self.cli("cancel", "budget/llm", "--holder", "author", "--request", "c", binary=BUDGET)
        self.assertEqual(p.returncode, 0)
        obj = self.assert_receipt(self.call(), 1)
        self.assertEqual((obj["outcome"], obj["used"], obj["text"]), ("cancelled", 0, None))
        self.assertEqual(self.sends(), 0)
        self.audit()

    def test_status_read_only(self):
        p = self.cli("status", "budget/llm", "--holder", "author", "--call", "absent")
        self.assertEqual(p.returncode, 0)
        self.assertFalse((self.node / "llmcall").exists())
        self.assertIsNone(json.loads(p.stdout)["request"])
        self.assert_receipt(self.call())
        before = tree(self.node)
        p = self.cli("status", "budget/llm", "--holder", "author", "--call", "c")
        obj = json.loads(p.stdout)
        self.assertEqual(p.returncode, 0)
        self.assertTrue(obj["raw_exists"])
        self.assertEqual(obj["raw_sha"], bg.sha(read_json(str(self.cd() / "raw.json"))))
        self.assertEqual((obj["gateway"]["stage"], obj["ledger"]["stage"]), ("done", "settled"))
        self.assertEqual(tree(self.node), before)

    def test_io_boundary(self):
        p = self.cli(*self.args(), env={"AOS7_TEST_FAULT": "open:*/req.json:EIO"})
        self.assertEqual((p.returncode, last_json(p)["outcome"], last_json(p)["stage"]), (3, "unknown", "io"))
        self.assertNotIn("Traceback", p.stderr)
        self.assertFalse((self.node / "llmcall").exists())
        self.assertEqual(self.audit()["seq"], 0)
        self.assert_receipt(self.call())
        p = self.call(extra=("--out", str(self.node)))
        self.assertEqual((p.returncode, last_json(p)["stage"]), (3, "io"))
        self.assertNotIn("Traceback", p.stderr)
        for exception in (Unknown("bad"), bg.LedgerDown("down"), OSError(errno.EIO, "io")):
            with patch("builtins.print") as printer:
                self.assertEqual(lc.io_boundary(lambda: (_ for _ in ()).throw(exception)), 3)
                obj = json.loads(next(c.args[0] for c in printer.call_args_list if "file" not in c.kwargs))
                self.assertEqual((obj["outcome"], obj["stage"]), ("unknown", "io"))

    def test_transport_exception_intent_kept(self):
        req = self.request("unknown.json", mode="unknown")
        p = self.call(req=req)
        self.assertEqual(p.returncode, 3, p.stderr)
        self.assertEqual(last_json(p)["outcome"], "unknown")
        self.assertNotIn("Traceback", p.stderr)
        self.assertEqual(self.sends(), 1)
        self.assertEqual(self.gw()["stage"], "intent")
        self.assertEqual(self.call(req=req).returncode, 3)
        self.assertEqual(self.sends(), 1)
        self.assertEqual(self.audit()["inflight"], R)

    def test_adopt_bad_file(self):
        for path in (self.node / "missing.json", self.node / "scalar.json"):
            if path.name == "scalar.json":
                write_json(str(path), [])
            before = tree(self.node)
            p = self.cli("adopt", "budget/llm", "--holder", "author", "--call", "c", "--raw", path)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(tree(self.node), before)


class TestLlmcallReplyShapes(unittest.TestCase):
    """〔llmcall〕I4：不合 status／usage 的終局計量，原樣 usage 與確定性時間。"""

    def test_bad_usage_and_status(self):
        key = bg.make_key("llm", "author", "c")
        for reply in (None, [], {"status": []}, {"status": "other", "usage": {"total_tokens": R}},
                      {"status": "reject", "billed": True, "usage": {"total_tokens": R}},
                      {"status": "ok", "usage": None}, {"status": "error", "usage": []},
                      *({"status": "ok", "usage": {"total_tokens": u}} for u in (True, -1, 1.5, "300", None))):
            with self.subTest(reply=reply):
                raw = {"call_id": "c", "reply": reply, "at": "fixed"}
                done = lc.done_from(raw, key, bg.kid_of(key), "digest", R)
                self.assertNotIn("used", done)
                self.assertEqual((done["billing"], done["overrun"], done["at"], done["raw_sha"]),
                                 ("pending", 0, "fixed", bg.sha(raw)))
                self.assertEqual(done["usage"], reply.get("usage") if isinstance(reply, dict) and
                                 isinstance(reply.get("usage"), dict) else None)

    def test_reject_ignores_usage(self):
        key = bg.make_key("llm", "author", "c")
        raw = {"call_id": "c", "reply": {"status": "reject", "billed": False, "usage": {"total_tokens": R + 10}}, "at": "fixed"}
        done = lc.done_from(raw, key, bg.kid_of(key), "digest", R)
        self.assertEqual((done["outcome"], done["used"], done["overrun"], done["billing"]), ("rejected", 0, 0, "final"))


if __name__ == "__main__":
    unittest.main()
