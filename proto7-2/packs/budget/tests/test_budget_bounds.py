"""budget 帳與 grant 測試。"""
from _budget_ledger import *  # noqa: F403

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
