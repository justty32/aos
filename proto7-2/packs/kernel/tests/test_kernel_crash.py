"""kernel 的送出、回條與崩潰恢復整合測試（kernel-pack §9 K11～K18）。"""
import os
import signal
import subprocess
import unittest

from kernelcase import CoreCase, FAKE, KernelMixin, PY, read_json, write_json


class CrashBase(KernelMixin, CoreCase):
    def setUp(self):
        super().setUp()
        self.setup_kernel()
        self.wait_pid(self.node, "brain")
        # 限定第一個 tock 發出決定，避免新 run 本來就會觸發另一筆 kill。
        self.cfg([self.kill_rule(until=1)])

    def _ok_tock(self, n, **kw):
        p = self.tock_kernel(n, **kw)
        self.assertEqual(p.returncode, 0, self.show(p))
        return self.state()

    def _crash_tock(self, n, point):
        p = self.tock_kernel(n, crash=point)
        self.assertEqual(p.returncode, -signal.SIGKILL, self.show(p))
        return self.state()

    def _pending(self, ident=None, sent=None):
        st = self.state()
        self.assertEqual(len(st["pending"]), 1, st)
        self.assertEqual(st["done"], [], st)
        p = st["pending"][0]
        if ident is not None:
            self.assertEqual(p["id"], ident)
        if sent is not None:
            self.assertIs(p["sent"], sent)
        return p

    def _done(self, intent, result):
        st = self.state()
        self.assertEqual(st["pending"], [], st)
        self.assertEqual(len(st["done"]), 1, st)
        d = st["done"][0]
        self.assertEqual((d["id"], d["op"], d["run"], d["result"]),
                         (intent["id"], "kill", intent["run"], result))
        return d

    def _receipt_for(self, intent, ok=True, msg="測試回條", **changes):
        r = dict(op="kill", id=intent["id"], run=intent["run"],
                 result={"ok": ok, "run": "brain#%d" % intent["run"], "msg": msg})
        r.update(changes)
        write_json(os.path.join(self.brain_slot(), "ctl-done.json"), r)
        return r

    def _alive_new_run(self, old_run):
        new_run = self.brain_run()
        self.assertGreater(new_run, old_run)
        pid = self.wait_pid(self.node, "brain")
        self.assertEqual(pid["run"], new_run)
        os.kill(pid["pid"], 0)
        self.assertIsNone(self.exit_of(self.node, "brain"))
        self.assertIsNone(self.ctl())
        return new_run

    def _consume_and_restart(self, intent):
        # 核心起新 run 會清 exit.json；暫緩 keep 一回合以讀到舊 run 的真實退出證據。
        tasks = self.tasks(self.node)
        self.set_tasks(self.node, [dict(t, enabled=False) for t in tasks])
        self.core_round()
        ex = self.wait_ended(self.node, "brain", run=intent["run"])
        self.assertEqual(ex["run"], intent["run"])
        self.assertIn(ex["code"], (-signal.SIGTERM, -signal.SIGKILL), ex)
        receipt = self.receipt()
        self.assertEqual((receipt["id"], receipt["op"], receipt["run"], receipt["result"]["ok"]),
                         (intent["id"], "kill", intent["run"], True))
        self.set_tasks(self.node, tasks)
        self.core_round()
        self._alive_new_run(intent["run"])
        self.assertEqual(self.receipt(), receipt)
        return receipt


class KernelCrash(CrashBase):
    def test_k11_before_state_replays_same_tock(self):
        """K11：⑤前殺掉不前進水位，同號 tock 重跑只提交一筆意圖。"""
        st = self._crash_tock(1, "kernel-before-state")
        self.assertEqual(st["last_tock"], 0)
        self.assertEqual(st["rev"], 0)
        self.assertEqual(st["rules"], {})
        self.assertEqual(st["pending"], [])
        self.assertIsNone(self.ctl())
        self._ok_tock(1)
        intent = self._pending(sent=True)
        self.assertEqual(self.state()["last_tock"], 1)
        self.assertEqual((self.ctl()["id"], self.ctl()["run"]), (intent["id"], intent["run"]))
        self._consume_and_restart(intent)
        self._ok_tock(2)
        self._done(intent, "ok")

    def test_k12_startup_sends_without_new_tock(self):
        """K12：⑤後殺掉，重起不等新 tock 就用原 id、run 與內容補送。"""
        self._crash_tock(1, "kernel-after-state")
        intent = self._pending(sent=False)
        self.assertIsNone(self.ctl())
        tock_path = os.path.join(self.kslot, "tock.json")
        old_tock = read_json(tock_path)
        p = subprocess.Popen([PY, "-B", FAKE, "run", "--rounds", "1"], cwd=self.node,
                             env=self.kenv(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
        self.procs.append(p)
        try:
            ctl = self.wait_for(self.ctl, msg="重起後沒有在等待 tock 前補送 ctl")
            self.assertEqual(ctl, {"op": "kill", "run": intent["run"], "id": intent["id"],
                                   "by": "kernel/kernel", "why": intent["why"]})
            self.wait_for(lambda: self.state()["pending"][0]["sent"])
            self._pending(ident=intent["id"], sent=True)
            self.assertEqual(read_json(tock_path), old_tock)
            self.assertIsNone(p.poll())
        finally:
            p.terminate()
            p.communicate(timeout=5)
        self.assertEqual(p.returncode, 0)

    def test_k13_after_ctl_keeps_id_then_settles(self):
        """K13：⑥後殺掉，既有 ctl 不造新 id，補記 sent 並以真回條完成。"""
        self._crash_tock(1, "kernel-after-ctl")
        intent = self._pending(sent=False)
        ctl = self.ctl()
        self.assertEqual((ctl["id"], ctl["run"]), (intent["id"], intent["run"]))
        self._ok_tock(2)
        self._pending(ident=intent["id"], sent=True)
        self.assertEqual(self.ctl(), ctl)
        self._consume_and_restart(intent)
        self._ok_tock(3)
        self._done(intent, "ok")

    def test_k13_core_finishes_before_kernel_restarts(self):
        """K13：崩潰後核心先 kill 並重起，kernel 從原回條恢復且新 run 沒被誤殺。"""
        self._crash_tock(1, "kernel-after-ctl")
        intent = self._pending(sent=False)
        self.core_round()
        self.assertEqual((self.receipt()["id"], self.receipt()["run"], self.receipt()["result"]["ok"]),
                         (intent["id"], intent["run"], True))
        new_run = self._alive_new_run(intent["run"])
        self._ok_tock(2)
        self._done(intent, "ok")
        self.core_round()
        self.assertEqual(self._alive_new_run(intent["run"]), new_run)

    def test_k14_receipt_recovers_before_settle_save(self):
        """K14：回條後存 state 前殺掉，重跑只恢復一筆 done，不再決定同 run。"""
        self._ok_tock(1)
        intent = self._pending(sent=True)
        self._consume_and_restart(intent)
        before = self.state()
        self._crash_tock(2, "kernel-before-settle-save")
        self.assertEqual(self.state(), before)
        self._ok_tock(2)
        self._done(intent, "ok")
        self._ok_tock(3)
        self._done(intent, "ok")
        self.assertIsNone(self.ctl())

    def _mismatched_receipt(self, field):
        self._crash_tock(1, "kernel-after-state")
        intent = self._pending(sent=False)
        changes = {"id": "別人的請求"} if field == "id" else {"op": "restart"} if field == "op" else {"run": intent["run"] + 1}
        r = self._receipt_for(intent, **changes)
        # 第三案刻意讓 result.run 相符，仍不能替代原請求 run。
        self.assertEqual(r["result"]["run"], "brain#%d" % intent["run"])
        self._ok_tock(2)
        self._pending(ident=intent["id"], sent=True)
        self.assertEqual((self.ctl()["id"], self.ctl()["run"]), (intent["id"], intent["run"]))

    def test_k15_receipt_wrong_id(self):
        """K15a：回條 id 不同不能認領成功，仍送原意圖。"""
        self._mismatched_receipt("id")

    def test_k15_receipt_wrong_op(self):
        """K15b：回條 op 不同不能認領成功，仍送原意圖。"""
        self._mismatched_receipt("op")

    def test_k15_receipt_wrong_request_run(self):
        """K15c：原請求 run 不符，即使 result.run 相符也不能認領。"""
        self._mismatched_receipt("run")

    def test_k15_matching_rejection(self):
        """K15d：原請求相符但核心拒絕 run，記 done rejected 並保留原因。"""
        self._crash_tock(1, "kernel-after-state")
        intent = self._pending(sent=False)
        msg = "指定的 run 1 已經不是現在的 run"
        self._receipt_for(intent, ok=False, msg=msg)
        self._ok_tock(2)
        self.assertEqual(self._done(intent, "rejected")["msg"], msg)
        self.assertIsNone(self.ctl())

    def _fault(self, n, rule):
        hits = os.path.join(self.root, "fault-hits.txt")
        self._ok_tock(n, extra={"AOS7_TEST_FAULT": rule, "AOS7_TEST_FAULT_HITS": hits})
        with open(hits, encoding="utf-8") as f:
            lines = f.read().splitlines()
        op, _, name = rule.split(":")
        self.assertTrue(any(line.startswith(op + "\t" + name + "\t") for line in lines), lines)

    def test_k16_write_ctl_failure_retries(self):
        """K16：寫 ctl 的 EIO 真正命中，pending 未送且有 wait，移除故障才送出。"""
        self._fault(1, "write:*/ctl.json:EIO")
        intent = self._pending(sent=False)
        self.assertIn("wait", intent)
        self.assertIsNone(self.ctl())
        self._ok_tock(2)
        self._pending(ident=intent["id"], sent=True)
        self.assertEqual(self.ctl()["id"], intent["id"])

    def test_k16_read_receipt_failure_waits(self):
        """K16：讀相符回條 EIO 時留 pending，恢復讀取後才記 done ok。"""
        self._ok_tock(1)
        intent = self._pending(sent=True)
        self._consume_and_restart(intent)
        self._fault(2, "open:*/ctl-done.json:EIO")
        self.assertIn("wait", self._pending(ident=intent["id"]))
        self.assertIsNone(self.ctl())
        self._ok_tock(3)
        self._done(intent, "ok")

    def test_k17_unknown_with_request_still_waits(self):
        """K17a：unknown 回條但同 id 請求還在，只留 pending 等核心。"""
        self._ok_tock(1)
        intent = self._pending(sent=True)
        ctl = self.ctl()
        self._receipt_for(intent, ok=False, msg="unknown：runner 仍在啟動")
        self._ok_tock(2)
        self._pending(ident=intent["id"], sent=True)
        self.assertEqual(self.ctl(), ctl)

    def test_k17_consumed_unknown_never_resends(self):
        """K17b：請求已消耗且回 unknown，記 done unknown，後續 tock 不重送。"""
        self._ok_tock(1)
        intent = self._pending(sent=True)
        self._receipt_for(intent, ok=False, msg="unknown：收完仍無法確定")
        # 模擬核心寫好回條後消耗請求，與請求仍留著的 K17a 對照。
        os.unlink(os.path.join(self.brain_slot(), "ctl.json"))
        for n in range(2, 5):
            self._ok_tock(n)
            self._done(intent, "unknown")
            self.assertIsNone(self.ctl())
        self.assertEqual(self.brain_run(), intent["run"])
        os.kill(self.wait_pid(self.node, "brain")["pid"], 0)

    def test_k18_changed_run_supersedes_unsent_intent(self):
        """K18：提交後送出前目標被人工 kill 換 run，舊意圖 superseded 且新 run 活著。"""
        self._crash_tock(1, "kernel-after-state")
        intent = self._pending(sent=False)
        pid = self.wait_pid(self.node, "brain")
        os.kill(pid["pid"], signal.SIGKILL)
        self.wait_ended(self.node, "brain", run=intent["run"])
        self.core_round()
        new_run = self._alive_new_run(intent["run"])
        self._ok_tock(2)
        self._done(intent, "superseded")
        self.core_round()
        self.assertEqual(self._alive_new_run(intent["run"]), new_run)

    def _triple_crash(self, point):
        original_run = self.brain_run()
        ident = None
        if point == "kernel-before-settle-save":
            self._ok_tock(1)
            intent = self._pending(sent=True)
            ident = intent["id"]
            receipt = self._consume_and_restart(intent)
        for i in range(3):
            # after-state 的水位已提交，後兩次須用下一個 tock 才能再命中⑤。
            n = i + 1 if point == "kernel-after-state" else 2 if point == "kernel-before-settle-save" else 1
            if point == "kernel-after-ctl" and i:
                # 核心尚未處理，模擬請求檔遺失，逼同一個意圖再次走寫 ctl 切點。
                os.unlink(os.path.join(self.brain_slot(), "ctl.json"))
            st = self._crash_tock(n, point)
            if point == "kernel-before-state":
                self.assertEqual(st["last_tock"], 0)
                self.assertEqual(st["pending"], [])
                self.assertIsNone(self.ctl())
            else:
                intent = self._pending(ident=ident)
                ident = intent["id"]
                self.assertEqual(intent["run"], original_run)
                if point == "kernel-before-settle-save":
                    self.assertEqual(self.receipt(), receipt)
        n = 4 if point == "kernel-after-state" else 2 if point == "kernel-before-settle-save" else 1 if point == "kernel-before-state" else 2
        self._ok_tock(n)
        if point != "kernel-before-settle-save":
            intent = self._pending(ident=ident, sent=True)
            receipt = self._consume_and_restart(intent)
            self._ok_tock(n + 1)
        self._done(intent, "ok")
        new_run = self._alive_new_run(original_run)
        for later in (n + 2, n + 3):
            self._ok_tock(later)
            self.core_round()
            self._done(intent, "ok")
            self.assertEqual(self._alive_new_run(original_run), new_run)
            self.assertEqual(self.receipt(), receipt)
        st = self.state()
        ids = [p["id"] for p in st["pending"] + st["done"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sum(d["op"] == "kill" and d["run"] == original_run for d in st["done"]), 1)
        self.assertEqual([name for name in os.listdir(self.brain_slot()) if name == "ctl-done.json"], ["ctl-done.json"])

    def test_k11_triple_sigkill_before_state(self):
        """K11 崩潰矩陣：⑤前連殺三次，最後只 kill 舊 run 一次且沒有重複 id。"""
        self._triple_crash("kernel-before-state")

    def test_k12_triple_sigkill_after_state(self):
        """K12 崩潰矩陣：⑤後連殺三次，最後只 kill 舊 run 一次且沒有重複 id。"""
        self._triple_crash("kernel-after-state")

    def test_k13_triple_sigkill_after_ctl(self):
        """K13 崩潰矩陣：⑥後同意圖連殺三次，最後只 kill 舊 run 一次且新 run 活著。"""
        self._triple_crash("kernel-after-ctl")

    def test_k14_triple_sigkill_before_settle_save(self):
        """K14 崩潰矩陣：回條存檔前連殺三次，恢復一筆 done 且不再送控制。"""
        self._triple_crash("kernel-before-settle-save")


class KernelReviewFixes(CrashBase):
    """astra 審查（KC1.review）高／中項的回歸案。"""

    def test_bad_receipt_never_resends(self):
        """審 1：ctl.json 已被消耗、回條壞掉＝不確定，pending 留著、不補送（K16 同類）。"""
        st = self._ok_tock(1)
        intent = self._pending(sent=True)
        os.unlink(os.path.join(self.brain_slot(), "ctl.json"))
        with open(os.path.join(self.brain_slot(), "ctl-done.json"), "w") as f:
            f.write("{壞")
        for n in (2, 3):
            st = self._ok_tock(n)
            self.assertIsNone(self.ctl())
            self.assertEqual([p["id"] for p in st["pending"]], [intent["id"]])
            self.assertIn("不補送", st["pending"][0]["wait"])

    def test_ok_receipt_for_other_run_not_success(self):
        """審 6：相符回條宣稱成功但 result.run 不是原 run＝不認成功；result 缺欄＝不結案。"""
        self._ok_tock(1)
        intent = self._pending(sent=True)
        os.unlink(os.path.join(self.brain_slot(), "ctl.json"))
        self._receipt_for(intent, ok=True, result={"ok": True, "run": "brain#%d" % (intent["run"] + 1), "msg": "x"})
        st = self._ok_tock(2)
        self.assertEqual(st["done"], [])
        self._receipt_for(intent, result={})
        st = self._ok_tock(3)
        self.assertEqual(st["done"], [])
        self._receipt_for(intent, ok=True)
        self._ok_tock(4)
        self._done(intent, "ok")

    def test_busy_target_defers_whole_round(self):
        """審 2：目標已有在途 kill 時，新 run 的 kill 整輪延後、規則狀態不存；在途的結案後下一個 tock 照樣提出。"""
        self.cfg([self.kill_rule()])
        self._ok_tock(1)
        intent = self._pending(sent=True)
        birth = self.birth(self.node, "brain")
        write_json(os.path.join(self.brain_slot(), "birth.json"), dict(birth, run=birth["run"] + 5))
        before = self.state()["rules"]
        st = self._ok_tock(2)
        self.assertEqual(st["rules"], before)
        self.assertEqual([p["id"] for p in st["pending"]], [intent["id"]])
        self.assertIn("延後", self.decisions()["note"])
        os.unlink(os.path.join(self.brain_slot(), "ctl.json"))
        self._receipt_for(intent, ok=False, msg="指定的 run 已經不是現在的")
        st = self._ok_tock(3)
        self.assertEqual([d["result"] for d in st["done"]], ["rejected"])
        self.assertEqual([p["run"] for p in st["pending"]], [birth["run"] + 5])

    def notify_rule(self, n=1):
        return {"name": "echo", "until": 1, "emit": [{"op": "notify", "target": "you", "text": "第 %d 封" % i,
                                                      "basis": {"age": 6}, "body": "## 做了什麼\n發現停住。\n\n"
                        "## 產出（檔案路徑 / commit / 分支）\n沒有產出，這封只是提醒。\n\n"
                        "## 沒做到、或證據不足的部分\n原因尚待確認。\n\n"
                        "## 需要對方或使用者決定的事\n請看紀錄。"} for i in range(n)]}

    def test_notify_without_mail_kept_in_done(self):
        """審 3：沒設 mail，在存 state 後被殺，重起後通知文字仍留在 done（logged）。"""
        self.cfg([self.notify_rule()])
        self._crash_tock(1, "kernel-after-state")
        st = self._ok_tock(2)
        self.assertEqual([(d["result"], d["text"]) for d in st["done"]], [("logged", "第 0 封")])
        self.assertEqual(st["done"][0]["basis"], {"age": 6})
        self.assertIn("## 做了什麼", st["done"][0]["body"])

    def test_notify_mail_once_across_sigkill(self):
        """通知經 mail：寄完、存 state 前被殺 ×3，收件匣只有一封 NEEDS-USER，信 id＝決定 id。"""
        self.cfg([self.notify_rule()], mail={"root": "..", "from": "kernel"})
        self._crash_tock(1, "kernel-after-state")
        for n in (2, 3, 4):
            self._crash_tock(n, "kernel-after-mail")
        st = self._ok_tock(5)
        self.assertEqual([d["result"] for d in st["done"]], ["sent"])
        box = os.path.join(self.root, "you", "inbox")
        letters = [f for f in os.listdir(box) if f.endswith(".md")]
        self.assertEqual(len(letters), 1, letters)
        text = open(os.path.join(box, letters[0]), encoding="utf-8").read()
        self.assertIn("status: NEEDS-USER", text)
        self.assertIn("id: %s" % st["done"][0]["id"], text)
        self.assertEqual(st['done'][0]['basis'], {'age': 6})
        self.assertIn('body', st['done'][0])
        self.assertEqual(text.count('## '), 4)
        for bad in ('無', 'kernel kernel', '{"'):
            self.assertNotIn(bad, text)

    def test_notify_mail_suppresses_new_mailbox_hint(self):
        self.cfg([self.notify_rule()], mail={'root': '..', 'from': 'kernel'})
        p = self.tock_kernel(1)
        self.assertEqual(p.returncode, 0, self.show(p))
        self.assertEqual(p.stderr, '')
        self.assertEqual(self.state()['done'][0]['result'], 'sent')

    def test_notify_cap_allows_new_candidates(self):
        """新候選不算在途；寄成功後下一輪仍能前進。"""
        self.cfg([dict(self.notify_rule(11), until=3, once=False)])
        for n in (1, 2, 3):
            st = self._ok_tock(n)
            self.assertEqual(st['pending'], [])
            self.assertIsNone(self.decisions()['note'])
        self.assertEqual(len(st['done']), 20)
        self.assertEqual([d['tock'] for d in st['done']], [2] * 9 + [3] * 11)

    def test_mail_failure_cap_recovers(self):
        import aos7_kernel as kernel
        from aos7_kernel_state import load_config, load_state
        self.cfg([dict(self.notify_rule(10), until=3, once=False)])
        cfg, sha = load_config(self.node, kernel.RULES | {'echo': lambda: None})
        state = load_state(self.kslot, sha)
        env = dict(task=self.kslot, node=self.node, node_id='a', tid='kernel')
        import kernel_fake
        state = kernel.one_tock(env, cfg, state, 1, lambda _: None, kernel_fake.RULES)
        from unittest.mock import patch
        with patch.object(kernel, 'settle_notify', return_value=('wait', '寄信失敗')):
            state = kernel.settle(env, cfg, state, lambda _: None)
        self.assertEqual(len(state['pending']), 10)
        blocked = kernel.one_tock(env, cfg, state, 2, lambda _: None, kernel_fake.RULES)
        self.assertEqual(blocked['pending'], state['pending'])
        self.assertIn('延後', self.decisions()['note'])
        state = kernel.settle(env, cfg, blocked, lambda _: None)
        state = kernel.one_tock(env, cfg, state, 3, lambda _: None, kernel_fake.RULES)
        self.assertEqual(len(state['pending']), 10)
        self.assertIsNone(self.decisions()['note'])


if __name__ == "__main__":
    unittest.main()
