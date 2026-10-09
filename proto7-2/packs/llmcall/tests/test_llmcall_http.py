"""真 HTTP 故障矩陣：一次受理、保留未知預留、完整回覆才結算。"""
import json
import os
import threading
import time
from unittest.mock import patch

from llmcallcase import LlmcallCase, R, last_json, read_json, write_json, tree
from fake_litellm import FakeLiteLLM, reply, truncate, close_no_length, drop, reset, late, drip, normal
import aos7_llmcall as lc

DEADLINE = .5
DELAY = .85
GAP = .3                # drip 段間隔 < DEADLINE，四段總時長 1.2 秒 > DEADLINE
# 子程序與 in-process 都不經 proxy，只連 127.0.0.1 的假伺服器。
NO_PROXY = {"http_proxy": "", "HTTP_PROXY": "", "all_proxy": "", "ALL_PROXY": "",
            "no_proxy": "127.0.0.1,localhost", "NO_PROXY": "127.0.0.1,localhost"}


class TestLlmcallHTTP(LlmcallCase):
    """〔llmcall〕七種故障各三變體，逐筆重放帳與驗證不重送。"""

    def up(self, *args, gateway="llm.litellm", **kw):
        return super().up(*args, gateway=gateway, **kw)

    def setUp(self):
        super().setUp()
        self.fake = FakeLiteLLM().start()
        self.addCleanup(self.fake.stop)
        self.env = dict(NO_PROXY, AOS7_LITELLM_URL=self.fake.url, AOS7_LITELLM_KEY="")
        self.body = {"model": "local-test", "messages": [{"role": "user", "content": "回 OK"}]}
        write_json(self.req, {"litellm": self.body})

    def call(self, c="c", **kw):
        return self.cli(*self.args(c, **kw), env=self.env)

    def balances(self, inflight, used):
        """獨立重放帳後，精確核對三個餘額。"""
        ledger = self.audit()
        self.assertEqual((ledger["inflight"], ledger["used"], ledger["available"]),
                         (inflight, used, ledger["initial"] - inflight - used))

    def evidence(self, c, p, rc, outcome, billing=None, stage=None):
        """核對 CLI 最後一行、入口階段與 raw／receipt 是否存在。"""
        self.assertEqual(p.returncode, rc, p.stdout + p.stderr)
        obj = last_json(p)
        self.assertEqual(obj["outcome"], outcome)
        if outcome == "unknown":
            self.assertEqual(obj["stage"], stage)
            self.assertEqual(self.gw(c)["stage"], "intent")
            has_raw = has_receipt = False
        else:
            self.assertEqual(obj["billing"], billing)
            self.assertEqual(self.gw(c)["stage"], "done")
            has_raw, has_receipt = True, billing != "pending"
            self.assertEqual(obj["used"], self.gw(c).get("used"))
            if billing == "pending":
                self.assertIsNone(obj["used"])
                self.assertIsNone(obj["settle"])
        self.assertEqual((self.cd(c) / "raw.json").exists(), has_raw)
        self.assertEqual((self.cd(c) / "receipt.json").exists(), has_receipt)
        return obj

    def replay(self, c, p, rc, outcome, billing=None):
        """重跑同 call_id 不增加 HTTP 請求；終局／pending 重印位元組相同。"""
        count = len(self.fake.bodies)
        files = tree(self.cd(c))
        gateway = self.gwpath(c).read_bytes()
        again = self.call(c)
        obj = self.evidence(c, again, rc, outcome, billing,
                            stage="intent" if outcome == "unknown" else None)
        self.assertEqual(len(self.fake.bodies), count)
        self.assertEqual(tree(self.cd(c)), files)
        self.assertEqual(self.gwpath(c).read_bytes(), gateway)
        if outcome != "unknown":
            self.assertEqual(again.stdout.encode(), p.stdout.encode())
        return obj

    def received(self, count):
        """精確核對受理數與送出的完整請求內容。"""
        self.assertEqual(self.fake.bodies, [self.body] * count)

    def test_timeout_x3_逾時保留預留(self):
        """正常 200、500、延後 drop 與 slow-drip 均超過 deadline，留下 intent。

        slow-drip 每段都在 socket timeout 內，只有外層 join(deadline) 能擋；拿掉就會落 raw 判成功。"""
        steps = [reply(200, normal(), DELAY), reply(500, {"error": "late"}, DELAY), drop(DELAY),
                 drip(GAP, normal())]
        for i, step in enumerate(steps, 1):
            with self.subTest(變體=step[0:2]):
                c = "timeout%d" % i
                self.fake.plan(step)
                start = time.monotonic()
                p = self.call(c, extra=("--deadline", DEADLINE))
                self.assertLess(time.monotonic() - start, DEADLINE + 3)
                self.evidence(c, p, 3, "unknown", stage="io")
                self.received(i)
                self.replay(c, p, 3, "unknown")
                self.balances(i * R, 0)

    def test_5xx_x3_伺服器失敗(self):
        """500／502／503 沒有 usage，保存 HTTP 碼且保留 pending。"""
        for i, code in enumerate((500, 502, 503), 1):
            with self.subTest(狀態碼=code):
                c = "server%d" % i
                self.fake.plan(reply(code, {"error": "down"}))
                p = self.call(c)
                self.evidence(c, p, 4, "failed", "pending")
                self.assertEqual(read_json(str(self.cd(c) / "raw.json"))["reply"]["http"], code)
                self.received(i)
                self.replay(c, p, 4, "failed", "pending")
                self.balances(i * R, 0)

    def test_bad_json_x3_壞內容(self):
        """破損 JSON、缺 choices 的陣列與 HTML 均 failed／pending，原內容保存。"""
        for i, data in enumerate((b"{broken", b"[]", b"<html>error</html>"), 1):
            with self.subTest(內容=data):
                c = "json%d" % i
                self.fake.plan(reply(200, data))
                p = self.call(c)
                self.evidence(c, p, 4, "failed", "pending")
                raw = read_json(str(self.cd(c) / "raw.json"))["reply"]
                # §5：合法 JSON 保存解析值，解析失敗保存原文字串。
                self.assertEqual(raw["response"], [] if data == b"[]" else data.decode())
                self.received(i)
                self.replay(c, p, 4, "failed", "pending")
                self.balances(i * R, 0)

    def test_missing_usage_x3_缺計量(self):
        """usage 不存在、null 或只有 prompt_tokens，回答 OK 但不結帳。"""
        variants = [normal(), dict(normal(), usage=None),
                    dict(normal(), usage={"prompt_tokens": 120})]
        variants[0].pop("usage")
        for i, response in enumerate(variants, 1):
            with self.subTest(變體=response):
                c = "usage%d" % i
                self.fake.plan(reply(200, response))
                p = self.call(c)
                obj = self.evidence(c, p, 4, "answered", "pending")
                self.assertEqual(obj["text"], "OK")
                self.assertIsNone(obj["used"])
                self.received(i)
                self.replay(c, p, 4, "answered", "pending")
                self.balances(i * R, 0)

    def test_truncated_x3_回覆截斷(self):
        """長度不足是 unknown；無長度的半份 JSON 是 pending；模型 length 可結算。"""
        data = json.dumps(normal()).encode()
        variants = [(truncate(200, data, len(data) // 2), 3, "unknown", None),
                    (close_no_length(200, data[:len(data) // 2]), 4, "failed", "pending"),
                    (reply(200, normal(finish_reason="length")), 0, "answered", "final")]
        for i, (step, rc, outcome, billing) in enumerate(variants, 1):
            with self.subTest(變體=step[0]):
                c = "truncated%d" % i
                self.fake.plan(step)
                p = self.call(c)
                obj = self.evidence(c, p, rc, outcome, billing,
                                    stage="io" if outcome == "unknown" else None)
                if i == 2:
                    self.assertEqual(read_json(str(self.cd(c) / "raw.json"))["reply"]["response"],
                                     data[:len(data) // 2].decode())
                if i == 3:
                    self.assertEqual((obj["text"], obj["used"]), ("OK", 120))
                    self.assertEqual(read_json(str(self.cd(c) / "raw.json"))["reply"]["finish_reason"],
                                     "length")
                self.received(i)
                self.replay(c, p, rc, outcome, billing)
                self.balances(min(i, 2) * R, 120 if i == 3 else 0)

    def test_disconnect_x3_受理後斷線(self):
        """drop、RST 與僅送 headers 都不能當成未送達退款。"""
        data = json.dumps(normal()).encode()
        for i, step in enumerate((drop(), reset(), truncate(200, data, 0)), 1):
            with self.subTest(變體=step[0]):
                c = "disconnect%d" % i
                self.fake.plan(step)
                p = self.call(c)
                self.evidence(c, p, 3, "unknown", stage="io")
                self.received(i)
                self.replay(c, p, 3, "unknown")
                self.balances(i * R, 0)

    def test_late_x3_遲到回覆人工接回(self):
        """遲到不自動成功；adopt 接回 U 小於、等於、大於 R 的回覆再結算。"""
        total_used = 0
        for i, usage in enumerate((120, R, R + 50), 1):
            with self.subTest(計量=usage):
                c = "late%d" % i
                response = normal(usage)
                self.fake.plan(late(DELAY, response))
                start = time.monotonic()
                p = self.call(c, extra=("--deadline", DEADLINE))
                self.evidence(c, p, 3, "unknown", stage="io")
                self.assertLess(time.monotonic() - start, DEADLINE + 3)
                self.received(i)
                self.wait_for(lambda: len(self.fake.late_sent) == i)
                sent_obj, sent_at = self.fake.late_sent[-1]
                self.assertEqual(sent_obj, response)
                self.assertGreater(sent_at, start + DEADLINE)
                self.replay(c, p, 3, "unknown")
                self.balances(R, total_used)
                req = read_json(str(self.cd(c) / "request.json"))
                supplied = {"call_id": c, "req_sha": req["req_sha"], "reply": {
                    "status": "ok", "billed": True, "body": "OK", "usage": {"total_tokens": usage}}}
                path = self.node / (c + "-adopt.json")
                write_json(str(path), supplied)
                adopted = self.cli("adopt", "budget/llm", "--holder", "author", "--call", c,
                                   "--raw", path, env=self.env)
                self.assertEqual(adopted.returncode, 0, adopted.stdout + adopted.stderr)
                self.assertEqual(last_json(adopted)["outcome"], "adopted")
                self.assertEqual(self.gw(c)["stage"], "intent")
                self.assertFalse((self.cd(c) / "receipt.json").exists())
                raw = read_json(str(self.cd(c) / "raw.json"))
                self.assertEqual((raw["source"], raw["reply"]), ("adopted", supplied["reply"]))
                rc, billing = (4, "overrun") if usage > R else (0, "final")
                done = self.call(c)
                obj = self.evidence(c, done, rc, "answered", billing)
                self.assertEqual((obj["text"], obj["used"], obj["overrun"]),
                                 ("OK", min(usage, R), max(0, usage - R)))
                self.replay(c, done, rc, "answered", billing)
                self.received(i)
                total_used += min(usage, R)
                self.balances(0, total_used)

    def test_in_process_drip_背景成功也不落檔(self):
        """slow-drip 讓背景傳輸在 deadline 後真的拿到完整 ok；send 仍丟 Unknown，也不寫任何檔。"""
        self.fake.plan(drip(GAP, normal()))
        before = tree(self.node)
        finished, results = threading.Event(), []
        transport = lc.TRANSPORT_LITELLM

        def observed(*args):
            try:
                results.append(transport(*args))
            finally:
                finished.set()

        with patch.dict(os.environ, self.env), patch.object(lc, "TRANSPORT_LITELLM", observed):
            start = time.monotonic()
            with self.assertRaises(lc.Unknown):
                lc.send(str(self.node), "direct", {"litellm": self.body}, DEADLINE)
            self.assertTrue(finished.wait(5), "傳輸 thread 應完成")
        self.assertGreater(self.fake.late_sent[0][1], start + DEADLINE)
        self.assertEqual((results[0]["status"], results[0]["usage"]), ("ok", {"total_tokens": 120}))
        self.received(1)
        self.assertEqual(tree(self.node), before)
        self.balances(0, 0)
