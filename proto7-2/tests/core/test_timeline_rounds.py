"""〔core〕關回合後讀取未知仍只結算一次；錯誤退避不忙轉、不溢位。"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from types import SimpleNamespace  # noqa: E402
from unittest.mock import Mock, patch  # noqa: E402

from base import CoreCase  # noqa: E402
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
