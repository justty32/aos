"""事件包按職責分組的測試。"""
from _events_store import *


class TestReviewRegressions(EventsCase):
    """astra E1 審查的回歸：快速路徑重用 seq、清段先刪了目的檔、rename 後多一段、keep 上限。"""

    def test_rotation_then_kill_does_not_reuse_seq(self):
        """must 單筆成段、ack 後輪替清段，寫等長新筆後被殺：恢復不可走快速路徑重用 seq（#1）。"""
        cfg = {"segment_bytes": 1, "keep_segments": 4}
        self.assertEqual(self.append(1, ch="must", config=cfg)["seq"], 1)
        store.ack(self.d, 1)
        code = ("import sys, os; sys.path.insert(0, %r); import aos7_events_store as s; "
                "os.environ['AOS7_TEST_CRASH'] = 'events:after-append'; "
                "s.append(%r, 'must', {'kind': 't', 'capture': 'published', 'event_id': 'e2', 'source': {}, "
                "'payload': {'i': 2}}, node='n')") % (EVENTS, self.d)
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, -9, p.stderr)
        r2 = self.append(2, ch="must")
        self.assertEqual((r2["seq"], r2["dup"]), (2, True))
        self.assertEqual(self.append(3, ch="must")["seq"], 3)
        rows = self.rows("must")
        self.assertEqual([r["event_id"] for r in rows if r["seq"] >= 2], ["e2", "e3"])
        self.assertEqual(len({r["seq"] for r in rows}), len(rows))

    def test_cleanup_never_deletes_destination(self):
        """目的段已存在時，must 容量清理前就回 unknown，目的檔原樣（#2）。"""
        self.append(1, ch="must", config={"segment_bytes": 1, "keep_segments": 1})
        dest = os.path.join(self.d, "must.000000000001.jsonl")
        with open(dest, "w") as f:
            f.write('{"seq": 1, "event_id": "other"}\n')
        before = self.contents()
        self.assertEqual(self.append(2, ch="must")["why"], "unknown")
        self.assertEqual(self.contents(), before)

    def test_rename_kill_with_full_obs_recovers_to_limit(self):
        """obs 已 4 段，rename 後被殺：下一次恢復就清回 4 段，檔數 ≤12（#3）。"""
        cfg = {"segment_bytes": 1, "keep_segments": 4}
        for i in range(1, 6):
            self.append(i, config=cfg)
        for i in range(1, 6):
            self.append(i, ch="must", config=cfg)
        self.assertEqual(len(self.channel()["segments"]), 4)
        code = ("import sys, os; sys.path.insert(0, %r); import aos7_events_store as s; "
                "os.environ['AOS7_TEST_CRASH'] = 'events:after-rename'; "
                "s.append(%r, 'obs', {'kind': 't', 'capture': 'published', 'event_id': 'e9', 'source': {}, "
                "'payload': {'i': 9}}, node='n')") % (EVENTS, self.d)
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, -9, p.stderr)
        self.assertEqual(self.append(9, ch="must")["why"], "full")   # 另一通道的 append 也會恢復
        self.assertLessEqual(len(os.listdir(self.d)), 12)
        self.assert_layout("obs")

    def test_keep_cap(self):
        """keep_segments 上限 4（12 檔硬約束）：store 拒絕、CLI 用法錯（#6）。"""
        with self.assertRaises(ValueError):
            self.append(1, config={"keep_segments": 5})
        p = subprocess.run([sys.executable, os.path.join(EVENTS, "aos7-events"), "--keep", "5"],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 2, p.stderr)



if __name__ == "__main__":
    unittest.main()
