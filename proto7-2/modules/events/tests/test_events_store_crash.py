"""事件包按職責分組的測試。"""
from _events_store import *


class TestCrash(EventsCase):
    def crash_cycles(self, point, ch, ack=False):
        env = dict(os.environ, DRIVER_ACK="1" if ack else "")
        progress = os.path.join(self.root, "progress.json")
        small = ch == "must" and not ack   # 只測寫入窗口；輪替／刪段要夠多筆才打得到
        n = 18 if small else 70
        killed = []
        for _ in range(3):
            target = (read_json(progress) or 0) + (2 if small else 12)
            p = subprocess.run([sys.executable, "-c", DRIVER, self.d, ch, str(n), str(target), point, progress],
                               capture_output=True, text=True, timeout=20, env=env)
            self.assertEqual(p.returncode, -9, p.stderr)
            done = read_json(progress) or 0
            self.assertLess(done, n)
            self.assertGreaterEqual(done + 1, target)
            killed.append(done + 1)
            # 每次被殺後立即恢復並驗不變量（不等整批續跑完才看，astra E1 #7）
            self.assertIsNotNone(store.recover(self.d, node="n"))
            self.assert_layout(ch)
        p = subprocess.run([sys.executable, "-c", DRIVER, self.d, ch, str(n), "0", "", progress],
                           capture_output=True, text=True, timeout=20, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(read_json(progress), n)
        self.assert_layout(ch)
        c, rows = self.channel(ch), self.rows(ch)
        ids = [r["event_id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))
        with open(progress + ".ok") as f:
            oks = [tuple(map(int, line.split())) for line in f]
        self.assertEqual([i for i, seq, dup in oks], list(range(1, n + 1)))
        for i, seq, dup in oks:
            if seq > c["dropped_upto"]:
                self.assertEqual(sum(r["event_id"] == "e%d" % i and r["seq"] == seq for r in rows), 1)
        if point == "events:after-partial":
            self.assertEqual(c["torn"], 3)
        if point == "events:after-append":
            self.assertEqual([i for i, seq, dup in oks if dup], killed)

    def test_after_append(self):
        self.crash_cycles("events:after-append", "must")

    def test_after_partial(self):
        self.crash_cycles("events:after-partial", "must")

    def test_after_rename(self):
        self.crash_cycles("events:after-rename", "obs")

    def test_after_unlink(self):
        self.crash_cycles("events:after-unlink", "obs")

    def test_after_unlink_must_acked(self):
        """must 有消費者跟上 ack：輪替刪已確認段時被殺 ×3，不丟未確認、不重 seq。"""
        self.crash_cycles("events:after-unlink", "must", ack=True)

    def test_after_rename_must_acked(self):
        self.crash_cycles("events:after-rename", "must", ack=True)



class TestTornCount(EventsCase):
    """V2：剛修掉半行就被殺，torn 不少記也不多記（截前、截後兩個點各 ×3）。"""
    def cycles(self, point):
        active = os.path.join(self.d, "must.active.jsonl")
        for k in range(1, 4):
            self.assertTrue(self.append(k, ch="must")["ok"])
            with open(active, "ab") as f:
                f.write(b'{"seq": 99, "half')
            code = "import sys; sys.path.insert(0, %r); import aos7_events_store as s; s.recover(%r, node='n')" % (EVENTS, self.d)
            p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20,
                               env=dict(os.environ, AOS7_TEST_CRASH=point))
            self.assertEqual(p.returncode, -9, p.stderr)
            self.assertIsNotNone(store.recover(self.d, node="n"))
            c = self.channel("must")
            self.assertEqual(c["torn"], k)
            self.assertNotIn("torn_cut", c)
            self.assert_layout("must")
        self.assertTrue(self.append(4, ch="must")["ok"])
        self.assertEqual(self.channel("must")["torn"], 3)

    def test_kill_before_truncate(self):
        self.cycles("events:after-torn-save")

    def test_kill_after_truncate(self):
        self.cycles("events:after-truncate")

    def test_stale_cut_not_reused(self):
        """截後被殺留下截點標記；下一次寫入在同一點又撕裂被殺，仍要再記一次。"""
        active = os.path.join(self.d, "must.active.jsonl")
        self.append(1, ch="must")
        with open(active, "ab") as f:
            f.write(b'{"half')
        rec = "{'kind': 't', 'capture': 'published', 'event_id': 'e2', 'source': {}, 'payload': {}}"
        for point, code in (("events:after-truncate", "s.recover(%r, node='n')" % self.d),
                            ("events:after-partial", "s.append(%r, 'must', %s, node='n')" % (self.d, rec))):
            p = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); "
                                "import aos7_events_store as s; " % EVENTS + code],
                               capture_output=True, text=True, timeout=20, env=dict(os.environ, AOS7_TEST_CRASH=point))
            self.assertEqual(p.returncode, -9, p.stderr)
        self.assertIsNotNone(store.recover(self.d, node="n"))
        self.assertEqual(self.channel("must")["torn"], 2)
        self.assertTrue(self.append(2, ch="must")["ok"])
        self.assert_layout("must")

    def test_bad_cut(self):
        self.append()
        st = read_json(os.path.join(self.d, "state.json"))
        for bad in ("x", None, -1):
            st["channels"]["obs"]["torn_cut"] = bad
            write_json(os.path.join(self.d, "state.json"), st)
            self.assertIsNone(store.recover(self.d, node="n"))
            self.assertEqual(read_json(os.path.join(self.d, "state.json")), st)



if __name__ == "__main__":
    unittest.main()
