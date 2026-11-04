"""astra 唯讀審查（notes/2026-09-24-impl/review-astra.md）kernel 側必修 P1～P4、P6、P7 的定點測試。

2026-09-24 one-boot：沒有 kernel 池了。P1（boot 等舊 kernel 池時舊 tick 又提交）改由 K/.tick.lock 擋：boot 拿著鎖時
一格 tick 退 75、什麼都不改；P2、P6 的「boot 等舊 kernel 池收乾淨」只剩舊的第 2 版帳本（K/state.json）才會走到。
"""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aos_home
import aos_kernel_boot
import aos_kernel_engine
import aos_kernel_info
import aos_kernel_store
from _kernel_fake import FakeCase


def legacy_home(case):
    """把 case 的 K 做成第 2 版帳本（K/state.json、帳本裡有 kernel 池），假 daemon 那邊 kernel 池 1 顆在跑。"""
    case.init()
    case.boot()
    case.settle()
    st = case.state()
    st.pop("ticker", None)
    st.pop("on", None)
    st["kcpu"] = "kernel/0"
    st["pools"]["kernel"] = dict(st["pools"]["default"], dpool="kernel", sent={"count": 1, "skip": []}, pending=None, free=[])
    case.fake._scale({"jsonrpc": "2.0", "id": "x", "method": "scale",
                      "params": {"pool": "kernel", "owner": str(case.K.absolute()), "count": 1, "skip": []}})
    for name in ("ledger.sqlite", "ledger.sqlite-wal", "ledger.sqlite-shm"):
        (case.K / name).unlink(missing_ok=True)
    aos_home.write_state(case.K, st)
    return st


class BootReread(FakeCase):
    """P1（one-boot 版）：boot 寫帳本、登記時拿著 K/.tick.lock，同時來的 tick 退 75、什麼都不改；
    舊 kernel cpu 裡還排著的舊格（帶 --chain／--seq）退 0、什麼都不改。boot 後不遺失、不重跑。"""

    def test_tick_during_boot_is_refused(self):
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        req = self.add("a", once=True)
        st = self.tick()
        key_a = st["on"]["a"]
        req_a = st["busy"][key_a]["req"]
        old_chain = st["chain"]
        self.respond(key_a)   # a 做完了（回音＋通知）
        self.add("c")         # 還沒登記
        real_call, fired = aos_kernel_boot._call, []

        def call(daemon, name, body, wait_ms):
            if not fired:
                before = self.state()
                fired.append(name)
                self.assertEqual(aos_kernel_engine.tick(self.K), aos_kernel_engine.BUSY_EXIT)
                self.assertEqual(aos_kernel_engine.tick(self.K, old_chain, 99), 0)
                self.assertEqual(self.state(), before)
            return real_call(daemon, name, body, wait_ms)

        with mock.patch.object(aos_kernel_boot, "_call", call):
            self.boot()
        self.assertEqual(fired, ["k-%s-boot-tick.json" % self.state()["chain"]])
        st = self.state()
        self.assertNotEqual(st["chain"], old_chain)
        self.assertEqual(st["recent"], [key_a])             # boot 後第一格查一次忙的
        st = self.ticks(2)
        self.assertIn("c", st["procs"])                     # 新登記的行程沒遺失
        self.assertNotIn("a", st["procs"])                  # 結清一次
        self.assertEqual(self.reply(req)["result"]["code"], 0)
        self.assertEqual(len([e for e in self.log_events() if e["event"] == "response" and e["proc"] == "a"]), 1)
        self.assertFalse((self.cpu(key_a) / "requests" / req_a).exists())  # 沒重跑


class BootDraining(FakeCase):
    """P2：舊帳本的 kernel 池縮 0 後摘要 count 0、running 0、draining 1（真 daemon 的形狀）時 boot 不寫新帳本。"""

    def test_boot_refuses_while_draining(self):
        old = legacy_home(self)
        self.fake.linger.add("kernel")
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            self.boot(wait_ms=200)
        self.assertEqual(cm.exception.code, "AlreadyRunning")
        self.assertIn("draining 1", cm.exception.msg)
        summary = self.fake.summary("kernel")
        self.assertEqual((summary["count"], summary["running"], summary["draining"]), (0, 0, 1))
        self.assertTrue(aos_kernel_store.legacy(self.K))
        self.assertEqual(aos_home.read_state(self.K)["chain"], old["chain"])


class BootRedeclare(FakeCase):
    """P3：舊鏈的 scale 回音照收、ack，但不能取消 boot 要求的整份重送。"""

    def _new_chain_sends(self, chain):
        return [e for e in self.log_events() if e["event"] == "scale_send" and e["pool"] == "default"
                and e["request"].startswith("k-%s-" % chain)]

    def test_old_success_echo_does_not_cancel(self):
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        self.edit_info(default={"count": 3})
        st = self.tick()  # 送 count 3、假 daemon 回成功，kernel 還沒收
        old = st["pools"]["default"]["pending"]["name"]
        self.assertTrue((Path(self.D) / "responses" / old).exists())
        self.boot()
        chain = self.state()["chain"]
        st = self.tick(process=False)
        self.assertIn({"event": "scale_echo", "pool": "default", "request": old, "result": "ok"}, self.log_events())
        self.assertEqual(len(self._new_chain_sends(chain)), 1)  # 集合相同也整份重送
        self.assertTrue(st["pools"]["default"]["pending"]["name"].startswith("k-%s-" % chain))
        st = self.ticks(2)
        entry = st["pools"]["default"]
        self.assertEqual((entry["sent"]["count"], entry["boot_redeclare"], entry["redeclare"]), (3, False, False))
        self.assertFalse((Path(self.D) / "responses" / old).exists())  # 舊回音 ack 掉了

    def test_old_error_echo_does_not_block(self):
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        self.fake.errors["default"] = ["TooMany"]
        self.edit_info(default={"count": 3})
        st = self.tick()  # 回 TooMany，kernel 還沒收
        old = st["pools"]["default"]["pending"]["name"]
        self.boot()
        chain = self.state()["chain"]
        st = self.tick(process=False)
        self.assertIn({"event": "scale_echo", "pool": "default", "request": old, "result": "TooMany"},
                      self.log_events())
        self.assertIsNone(st["pools"]["default"]["error"])
        self.assertEqual(len(self._new_chain_sends(chain)), 1)
        st = self.ticks(2)
        entry = st["pools"]["default"]
        self.assertEqual((entry["sent"]["count"], entry["error"]), (3, None))
        self.assertFalse((Path(self.D) / "responses" / old).exists())


class NameTakenMove(FakeCase):
    """P4：初次宣告撞到別人的池（NameTaken）→ 人改 dpool → 直接換新位置，不向別人的池送縮 0。"""

    def test_rename_after_real_owner_conflict(self):
        taken = Path(self.D) / "pools" / "taken"
        taken.mkdir(parents=True)
        aos_home.write_json(taken / "pool.json", {"pool": "taken", "owner": "/abs/other", "count": 1, "skip": [],
                                                  "ver": 1, "decl": None})
        aos_home.write_json(taken / "summary.json", {"pool": "taken", "owner": "/abs/other", "count": 1, "ver": 1,
                                                     "running": 1, "killing": 0, "draining": 0})
        self.init({"default": {"count": 2, "dpool": "taken"}})
        self.boot()
        st = self.settle()
        self.assertEqual(st["pools"]["default"]["error"]["code"], "NameTaken")
        self.edit_info(default={"count": 2, "dpool": "free-name"})
        st = self.settle()
        entry = st["pools"]["default"]
        self.assertEqual((entry["dpool"], entry["sent"]["count"], entry["error"]), ("free-name", 2, None))
        self.assertEqual(self.fake.pool("free-name")["count"], 2)
        self.assertEqual([p for _, p in self.fake.seen if p.get("pool") == "taken" and p["count"] == 0], [])
        self.assertEqual(self.fake.pool("taken")["owner"], "/abs/other")
        self.assertIn("pool_abandon", [e["event"] for e in self.log_events()])


class UnknownSummary(FakeCase):
    """P6：summary.json 在但讀不到時，搬池、boot、halt 都不前進。"""

    def test_move_waits_on_unreadable_summary(self):
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        self.fake.garble.add("default")
        self.edit_info(default={"count": 2, "dpool": "k2-default"})
        st = self.ticks(4)
        self.assertEqual(st["pools"]["default"]["dpool"], "default")
        self.assertIsNone(self.fake.pool("k2-default"))
        self.assertIn("pool_summary_unknown", [e["event"] for e in self.log_events()])
        self.fake.gone("default")
        st = self.ticks(3)
        self.assertEqual(st["pools"]["default"]["dpool"], "k2-default")
        self.assertEqual(self.fake.pool("k2-default")["count"], 2)

    def test_boot_waits_on_unreadable_summary(self):
        """舊帳本的 kernel 池縮 0 後摘要讀不到：當還在，boot 不寫新帳本。"""
        old = legacy_home(self)
        self.fake.garble.add("kernel")
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            self.boot(wait_ms=200)
        self.assertEqual(cm.exception.code, "AlreadyRunning")
        self.assertIn("讀不到", cm.exception.msg)
        self.assertTrue(aos_kernel_store.legacy(self.K))
        self.assertEqual(aos_home.read_state(self.K)["chain"], old["chain"])

    def test_halt_waits_on_unreadable_summary(self):
        self.init({"default": {"count": 1}})
        self.boot()
        self.settle()
        self.fake.garble.add("default")
        self.stop_kernel()
        st = self.ticks(5)
        self.assertEqual(st["phase"], "stopped")
        with self.assertRaises(aos_kernel_info.KernelError) as cm:
            with contextlib.redirect_stdout(io.StringIO()):
                aos_kernel_boot.stop(self.K, wait_ms=200)
        self.assertEqual(cm.exception.code, "Timeout")
        self.assertIn("讀不到", cm.exception.msg)
        self.fake.gone("default")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            aos_kernel_boot.stop(self.K, wait_ms=1000)
        self.assertEqual(out.getvalue().strip(), "stopped")


class BadNotifyParse(FakeCase):
    """P7：home 解析本身會拋例外的通知也只刪、log 一行，這格不退 1。"""

    def test_nul_and_huge_number(self):
        self.init({"default": {"count": 2}})
        self.boot()
        self.settle()
        self.add("a")
        st = self.tick()
        key = st["on"]["a"]
        cpus = self.cpu(key).parent
        for n, home in enumerate(["/x\u0000y", "%s/%s" % (cpus, "9" * 5000), "%s/1\u0000" % cpus]):
            aos_home.write_json(self.K / "requests" / ("resp-p7-%d.json" % n),
                                {"jsonrpc": "2.0", "method": "responded", "params": {"home": home, "name": "x"}})
        st = self.tick()  # tick() 裡檢查退出碼 0
        self.assertEqual(list((self.K / "requests").glob("resp-*")), [])
        bad = [e for e in self.log_events() if e["event"] == "bad_notify"]
        self.assertEqual(sorted(e["file"] for e in bad), ["resp-p7-%d.json" % n for n in range(3)])
        self.assertIn(key, st["busy"])
        self.assertIsNone(aos_kernel_info.split_key("default/" + "1" * 19))
        self.assertEqual(aos_kernel_info.split_key("default/" + "1" * 18), ("default", int("1" * 18)))


if __name__ == "__main__":
    unittest.main()
