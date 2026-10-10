"""〔core〕關回合後讀取未知仍只結算一次；錯誤退避不忙轉、不溢位。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from types import SimpleNamespace  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402

from base import CoreCase  # noqa: E402
import aos7_daemon
from aos7_fs import read_json, write_json
import aos7_daemon_timeline as timeline  # noqa: E402

class TestTimelineRounds(CoreCase):
    def make_timeline(self):
        self.mknode("a", interval_ms=0)
        d = SimpleNamespace(root=self.root, gen=1, stopping=False, stopping_since=None,
                            kill_on_stop=False, is_paused=Mock(return_value=False), round_done=Mock(),
                            log=Mock(), kill_live=Mock())
        return timeline.Timeline(d, "a", None)

    def test_unknown_after_tock_counts_once(self):
        # glob 可區分 daemon 與 tock 路徑，卻無單次讀取鉤子；用固定序列避開中途開關的競速。
        for recovered in (False, True):
            with self.subTest(recovered=recovered):
                tl = self.make_timeline()
                for rnd in (1, 2):   # 下一組倒數也不能吃到上一回合殘留的欠帳
                    tl.d.stopping = False
                    tl.d.round_done.reset_mock()

                    def paused(_nid):
                        if tl.d.round_done.called:
                            tl.d.stopping = True
                            return True
                        return False

                    reads = [False, None, None, True, False, False] if recovered else [False, None, None, False, False, False, False]
                    with patch.object(tl.d, "is_paused", side_effect=paused), \
                            patch.object(tl, "check_round", side_effect=reads), \
                            patch.object(tl, "prog", return_value=(0, {"round": rnd}, "")) as prog:
                        tl._loop()
                    tl.d.round_done.assert_called_once_with("a")
                    self.assertEqual([c.args[0] for c in prog.call_args_list].count("aos7-tick"), 1)
                    self.assertEqual(tl.phase, "paused")
                    self.assertEqual(tl.round, rnd)
                    self.assertIsNone(tl.owe_round)

    def test_owe_base_unchanged_clears_without_debit(self):
        node = self.mknode("a", interval_ms=0)
        write_json(os.path.join(node, ".aos", "round.json"), {"round": 4, "open": False})
        path = os.path.join(self.root, ".aosd", "paused.json")
        write_json(path, {"paused": {}, "steps": {"a": {"k": 2}}, "owe": {"a": 4}})
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        d.load_state()
        tl = timeline.Timeline(d, "a", None)
        original = d.round_done

        def settled(nid, debit=True):
            original(nid, debit=debit)
            d.stopping = True

        with patch.object(d, "round_done", side_effect=settled) as done, patch.object(tl, "prog") as prog:
            tl._loop()
        done.assert_called_once_with("a", debit=False)
        prog.assert_not_called()
        self.assertEqual(read_json(path), {"paused": {}, "steps": {"a": {"k": 2}}})
        self.assertEqual(d.owe, {})

    def test_failed_tick_clears_durable_owe_before_backoff(self):
        tl = self.make_timeline()
        tl.d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, tl.d.rfd)
        tl.d.steps = {"a": {"k": 2}}
        with patch.object(tl, "prog", return_value=(1, None, "failed")), \
                patch.object(tl, "backoff", side_effect=lambda: setattr(tl.d, "stopping", True)):
            tl._loop()
            self.assertEqual(read_json(os.path.join(tl.d.aosd, "paused.json")),
                             {"paused": {}, "steps": {"a": {"k": 2}}})

    def test_control_discards_stale_owe_before_timeline_settlement(self):
        tl = self.make_timeline()
        write_json(os.path.join(tl.node, ".aos", "round.json"), {"round": 5, "open": False})
        tl.d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, tl.d.rfd)
        for op in (tl.d.op_pause, tl.d.op_resume):
            tl.d.owe, tl.owe_base = {"a": 4}, 4
            self.assertTrue(op("a", {"owner": "k", "rounds": 2})[0])
            self.assertNotIn("owe", read_json(os.path.join(tl.d.aosd, "paused.json")))
        with patch.object(tl, "prog", return_value=(0, {"stale": True}, "")), \
                patch.object(tl.d, "round_done", wraps=tl.d.round_done) as done:
            tl._loop()
            done.assert_not_called()
        self.assertEqual(tl.d.steps, {"a": {"k": 2}})

    def test_checked_round_drives_settlement_and_mark_owe(self):
        for base in (None, 4):
            tl = self.make_timeline()
            tl.owe_base, tl.d.owe = base, {"a": base}
            tl.d.mark_owe = Mock()
            tl.d.round_done.side_effect = lambda *a, **kw: setattr(tl.d, "stopping", True)
            with patch.object(timeline, "read_round", return_value=(timeline.ROUND_CLOSED, {"round": 4}, None)), \
                    patch.object(tl, "disk_round", return_value=99), \
                    patch.object(tl, "prog", return_value=(0, {"stale": True}, "")):
                tl._loop()
            if base is None:
                tl.d.mark_owe.assert_called_once_with("a", 4)
            else:
                tl.d.round_done.assert_called_once_with("a", debit=False)

    def test_save_failure_retries_settlement_before_mark_owe(self):
        # 每個入口先存失敗兩次；mark_owe／tick 都不能越過尚未落盤的結算。
        for route in ("pending", "owe_round", "owe_base", "recovered", "tick_failed", "closed"):
            with self.subTest(route=route):
                tl = self.make_timeline()
                tl.d.mark_owe = Mock(return_value=True)
                tl.checked_round = 5
                tl.d.owe = {"a": 4}
                if route == "pending":
                    tl.settle_pending = False
                elif route == "owe_round":
                    tl.owe_round = 5
                elif route == "owe_base":
                    tl.owe_base = 4
                elif route == "recovered":
                    tl.owe_round = 5
                debit = route != "pending" and route != "tick_failed"
                marks = 1 if route in ("tick_failed", "closed") else 0
                attempts = []

                def settle(_nid, debit=True):
                    attempts.append(debit)
                    self.assertEqual(tl.d.mark_owe.call_count, marks)
                    self.assertEqual(prog.call_count, {"recovered": 1, "tick_failed": 1,
                                                      "closed": 2}.get(route, 0))
                    if len(attempts) < 3:
                        if route in ("owe_round", "recovered"):
                            self.assertEqual(tl.owe_round, 5)
                        if route == "owe_base":
                            self.assertEqual(tl.owe_base, 4)
                        return False
                    tl.d.stopping = True
                    return True

                reads = [True, False] if route == "recovered" else []
                reads += [False] * 12
                reply = (1, None, "failed") if route == "tick_failed" else (0, {"round": 5}, "")
                with patch.object(tl.d, "round_done", side_effect=settle), \
                        patch.object(tl, "check_round", side_effect=reads), \
                        patch.object(tl, "prog", return_value=reply) as prog, \
                        patch.object(tl, "backoff") as backoff, \
                        patch.object(tl, "sleep_until") as sleep, \
                        patch.object(tl.wake, "wait") as wait:
                    tl._loop()
                self.assertEqual(attempts, [debit] * 3)
                self.assertIsNone(tl.settle_pending)
                self.assertIsNone(tl.owe_round)
                self.assertIsNone(tl.owe_base)
                self.assertEqual(backoff.call_count, 1 if route == "tick_failed" else 0)
                self.assertGreaterEqual(wait.call_count, 1)
                sleep.assert_not_called()

    def test_open_round_recovers_before_pending_settlement(self):
        for owed in (None, "base", "round"):
            with self.subTest(owed=owed):
                tl = self.make_timeline()
                tl.settle_pending = False
                if owed == "base":
                    tl.owe_base, tl.d.owe = 4, {"a": 4}
                elif owed == "round":
                    tl.owe_round = 5
                tl.d.mark_owe = Mock(return_value=True)
                actions = []

                def prog(*args):
                    actions.append("tock")
                    return 0, {}, ""

                def done(_nid, debit=True):
                    actions.append("settle")
                    self.assertFalse(debit)
                    tl.d.stopping = True
                    return True

                with patch.object(tl, "check_round", side_effect=[True, False]), \
                        patch.object(tl, "prog", side_effect=prog), \
                        patch.object(tl.d, "round_done", side_effect=done):
                    tl._loop()
                self.assertEqual(actions, ["tock", "settle"])
                self.assertIsNone(tl.settle_pending)
                self.assertIsNone(tl.owe_base)
                self.assertIsNone(tl.owe_round)
                tl.d.mark_owe.assert_not_called()

    def test_backoff_clears_wake_and_caps_exponent(self):
        for fails in (0, 10 ** 4):   # 分別抓忙轉與大指數溢位
            with self.subTest(fails=fails):
                tl = self.make_timeline()
                tl.recover_fails = fails
                tl.kick = 123
                tl.wake.set()
                with patch.object(timeline, "RECOVER_BACKOFF_MAX", 0.03), \
                        patch.object(tl.wake, "wait", wraps=tl.wake.wait) as wait:
                    tl.backoff()
                self.assertGreater(wait.call_count, 0)
                self.assertLess(wait.call_count, 50)
                self.assertFalse(tl.wake.is_set())
                self.assertEqual(tl.kick, 123)
